import os
import sys
import time
import json
import glob
import pathlib
import numpy as np
import os.path as osp
from PyQt5 import QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QMimeData
from PyQt5.QtGui import QKeySequence, QDropEvent, QDragEnterEvent, QMouseEvent, QDrag
from PyQt5.QtWidgets import (QApplication, QWidget, QPushButton,QLineEdit,
                             QDialogButtonBox, QMenu,QAction, QMenuBar, QLabel,
                             QVBoxLayout,QDialog, QFileDialog, QStatusBar, QListWidget, 
                             QMainWindow, QHBoxLayout, QGridLayout, QMessageBox, QShortcut,
                             QListWidgetItem, QSizePolicy, QFormLayout, QFrame, QTreeWidget,
                             QTreeWidgetItem, QComboBox)

from OCC.Extend import TopologyUtils
from OCC.Core.TopAbs import TopAbs_FACE
from OCC.Core.AIS import AIS_ColoredShape
from OCC.Display.OCCViewer import rgb_color
from OCC.Display.backend import load_backend
from OCC.Core.BRepCheck import BRepCheck_Analyzer
from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Extend.TopologyUtils import TopologyExplorer
from OCC.Core.GeomAbs import (GeomAbs_Plane, GeomAbs_Cylinder, GeomAbs_Cone, 
                              GeomAbs_Sphere, GeomAbs_Torus, GeomAbs_BezierSurface,
                              GeomAbs_BSplineSurface, GeomAbs_SurfaceOfRevolution,
                              GeomAbs_SurfaceOfExtrusion, GeomAbs_OffsetSurface,
                              GeomAbs_OtherSurface)
load_backend("qt-pyqt5")
import OCC.Display.qtDisplay as qtDisplay

"""
数模标注工具
界面待更新：
1   1. 5个按键，3/5块显示                                                    1
1   2. 最大化问题                                                            3
    3. 实例分割标注
    4. 每个界面显示一个标题

功能待更新：
1   1. 打开文件                                     按键1
1   2. 打开文件夹，并打开文件夹中的文件，             按键2
        该文件为最近的历史记录或文件夹中第一个文件
1   3. 显示数模                                     显示1
1   4. 显示数模面序列                               显示2
1   5. 选中面                                       显示界面操作
        1) 单击数模选中
        2) 单击面序列选中
    6. 标注面，右键弹出标记为，或者双击？             显示界面操作
1       1) 面序列右键
1       2) 数模右键                                                          2
1   7. 显示标签                                     显示3                    1
        1) 左键标签，高亮且关联面列表及数模展示窗口，
        面高亮时，对应标签高亮
        2) 右键菜单，包括修改及删除
1   8. 上一个                                       按键3                    2
1   9. 下一个                                       按键4                    2    
1   10. 自动保存标注结果                             代码                     1    
1   11. 清除                                        按键5
1   12. 快捷键                                      操作                     3
1   13. 文件列表                                    显示4

bug待修复: 
1   1. 单击打开文件后，不选择文件，直接关闭，则面高亮失效！                      3
1   2. 未识别非法的标签

2024.5.9  赵家奇

注：语义面和实例面一一对应，一个实例有一个底面，且一一对应
1. 标注实例
    1) 未匹配一个面对应多个特征的情况
    2) 单面特征如何给标签赋值
    3) 功能：修改、删除、拖拽
2. 底面标注
    1) 如何确认底面
    2) 功能：修改、删除
3. 面显示分层
"""

class TopologyChecker():
    # modified from BREPNET: https://github.com/AutodeskAILab/BRepNet/blob/master/pipeline/extract_brepnet_data_from_step.py
    def __init__(self):
        pass

    def find_edges_from_wires(self, top_exp):
        edge_set = set()
        for wire in top_exp.wires():
            wire_exp = TopologyUtils.WireExplorer(wire)
            for edge in wire_exp.ordered_edges():
                edge_set.add(edge)
        return edge_set

    def find_edges_from_top_exp(self, top_exp):
        edge_set = set(top_exp.edges())
        return edge_set

    def check_closed(self, body):
        # In Open Cascade, unlinked (open) edges can be identified
        # as they appear in the edges iterator when ignore_orientation=False
        # but are not present in any wire
        top_exp = TopologyUtils.TopologyExplorer(body, ignore_orientation=False)
        edges_from_wires = self.find_edges_from_wires(top_exp)
        edges_from_top_exp = self.find_edges_from_top_exp(top_exp)
        missing_edges = edges_from_top_exp - edges_from_wires
        return len(missing_edges) == 0

    def check_manifold(self, top_exp):
        faces = set()
        for shell in top_exp.shells():
            for face in top_exp._loop_topo(TopAbs_FACE, shell):
                if face in faces:
                    return False
                faces.add(face)
        return True

    def check_unique_coedges(self, top_exp):
        coedge_set = set()
        for loop in top_exp.wires():
            wire_exp = TopologyUtils.WireExplorer(loop)
            for coedge in wire_exp.ordered_edges():
                orientation = coedge.Orientation()
                tup = (coedge, orientation)
                # We want to detect the case where the coedges
                # are not unique
                if tup in coedge_set:
                    return False
                coedge_set.add(tup)
        return True

    def __call__(self, body):
        top_exp = TopologyUtils.TopologyExplorer(body, ignore_orientation=True)
        if top_exp.number_of_faces() == 0:
            print('Empty shape') 
            return False
        # OCC.BRepCheck, perform topology and geometricals check
        analyzer = BRepCheck_Analyzer(body)
        if not analyzer.IsValid(body):
            print('BRepCheck_Analyzer found defects') 
            return False
        # other topology check
        if not self.check_manifold(top_exp):
            print("Non-manifold bodies are not supported")
            return False
        if not self.check_closed(body):
            print("Bodies which are not closed are not supported")
            return False
        if not self.check_unique_coedges(top_exp):
            print("Bodies where the same coedge is uses in multiple loops are not supported")
            return False
        return True

def load_body_from_step(step_file):
    """
    Load the body from the step file.  
    We expect only one body in each file
    """
    assert pathlib.Path(step_file).suffix in ['.step', '.stp', '.STEP', '.STP']
    reader = STEPControl_Reader()
    reader.ReadFile(str(step_file))
    reader.TransferRoots()
    shape = reader.OneShape()
    return shape

class ErrorInputDialog(QDialog):
    def __init__(self, item_text):
        super().__init__()
        self.initUI(item_text)

    def initUI(self, item_text, title = "发生错误"):
        layout = QVBoxLayout()
        label = QLabel(f"{item_text}")
        layout.addWidget(label)
        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok)
        buttonBox.accepted.connect(self.accept)
        layout.addWidget(buttonBox)
        self.setLayout(layout)
        self.setWindowTitle(title)

class CustomInputDialog(QDialog):
    def __init__(self, item_text, title = "请输入语义标签"):
        super().__init__()
        self.initUI(item_text, title)

    def initUI(self, item_text, title):
        layout = QVBoxLayout()
        label = QLabel(f"{item_text}")
        layout.addWidget(label)
        self.lineEdit = QLineEdit()
        layout.addWidget(self.lineEdit)

        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        layout.addWidget(buttonBox)

        self.setLayout(layout)
        self.setWindowTitle(title)

    def getTextInput(self):
        return self.lineEdit.text()

class BotLabelInputDialog(QDialog):
    def __init__(self, item_text, faces_id, title = "请选择底面"):
        super().__init__()
        self.initUI(item_text, faces_id, title)

    def initUI(self, item_text, faces_id, title):
        layout = QVBoxLayout()
        label = QLabel(f"{item_text}")
        layout.addWidget(label)
        self.comboBox = QComboBox()
        for fid in faces_id:
            self.comboBox.addItem(f"{fid}")
        layout.addWidget(self.comboBox)

        buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        layout.addWidget(buttonBox)

        self.setLayout(layout)
        self.setWindowTitle(title)

    def getBotLabelInput(self):
        return int(self.comboBox.currentText())

# class QTreeWidgetItem(QTreeWidgetItem):
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.setFlags(self.flags() | Qt.ItemIsDragEnabled)

"""重写QTreeWidget部分方法，实现子项拖拽"""
class CustomTreeWidget(QTreeWidget):
    itemMovedManually = pyqtSignal(QTreeWidgetItem, QTreeWidgetItem)
    def __init__(self, *args):
        super().__init__(*args)
        # self.setDragDropMode(QTreeWidget.NoDragDrop)  
        # self.setSelectionMode(QTreeWidget.SingleSelection)
        # self.setSelectionMode(QTreeWidget.ExtendedSelection)
        # self.setDragEnabled(False)

        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setSelectionMode(self.SingleSelection)
        self.setDragDropMode(self.InternalMove)
        self.dragStartPosition = QPoint()
        self.currentlyDraggedItem = None

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton:
            item = self.itemAt(event.pos())
            # 只允许子项被拖动
            if item and item.parent():
                self.dragStartPosition = event.pos()
                self.currentlyDraggedItem = item
                event.accept()  # 接受事件防止默认处理
            else:
                event.ignore()  # 忽略顶级项的点击事件
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() & Qt.LeftButton and self.currentlyDraggedItem:
            if (event.pos() - self.dragStartPosition).manhattanLength() < QApplication.startDragDistance():
                return
            # 手动实现拖动效果
            mimeData = QMimeData()
            mimeData.setText(self.currentlyDraggedItem.text(0))  # 示例：将项的文本作为拖放数据
            drag = QDrag(self)
            drag.setMimeData(mimeData)
            drag.setPixmap(QLabel("Drag Icon").grab())  # 可以替换为适当的图标
            drag.setHotSpot(event.pos() - self.mapFromGlobal(event.globalPos()))
            drag.exec_(Qt.CopyAction | Qt.MoveAction)
        else:
            event.ignore()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.currentlyDraggedItem = None
        super().mouseReleaseEvent(event)
    """def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.LeftButton and self.movingItem:
            source_item = self.movingItem
            # 获取释放位置的项
            release_item = self.itemAt(event.pos())
            release_parent = release_item.parent() if release_item else None
            # viewport_rect = self.viewport().geometry()
            if not release_item:
                # 在空白区域
                release_parent = source_item
                self.itemMovedManually.emit(source_item, release_parent)
            elif release_item and release_parent != source_item.parent():
                # 在其他父项区域，移动子项
                # 如果release_parent为空，则release_item为父项
                if not release_parent:
                    release_parent = release_item
                self.itemMovedManually.emit(source_item, release_parent)
            else:
                # 返回原位，实际上不需要处理，因为我们禁用了默认的拖放
                pass
        self.currentlyDraggedItem = None  # 释放时重置
        self.movingItem = None
        super().mouseReleaseEvent(event) """

    def mimeData(self, items):
        # 实现mimeData方法，以便支持拖放
        mime_data = super().mimeData(items)
        return mime_data

    """dropEvent"""
    def dragEnterEvent(self, event: QDragEnterEvent):
        # 允许拖动进入
        if event.mimeData().hasText():
            # event.mimeData().hasFormat('application/x-qabstractitemmodeldatalist'):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        # super().dropEvent(event)
        # 获取源item
        selected_items = self.selectedItems()
        if selected_items:
            source_item = selected_items[0]
        else:
            return
        source_parent = source_item.parent()
        # 若移动项为父项则忽略
        if not source_parent:
            event.ignore()
            self.currentItemBeingDragged = None
            return
        # 获取当前drop位置的item和其父item
        dest_item = self.itemAt(event.pos())
        dest_parent = dest_item.parent() if dest_item else None
        # # 如果drop在空白区域，则创建新的父项
        # rect = self.viewport().geometry()
        if not dest_item: # and not rect.contains(event.pos()):
            dest_parent = source_item
            dest_item = source_item
        elif not dest_parent:
            dest_parent = dest_item
        # 如果
        # 如果源item和目标item相同或目标是源的子项，不移动
        elif source_parent == dest_parent:
            event.ignore()
            return
        # 空白区域：source_item、source_item、source_item
        # 拖至主项：source_item、dest_parent、dest_parent
        # 拖至子项：source_item、dest_parent、dest_item
        self.itemMovedManually.emit(source_item, dest_parent)  # 发射信号
        # event.acceptProposedAction()
    

class LabelShapeV0(object):
    def __init__(self):
        super().__init__()
        self.widget = QWidget()
        # 数模展示窗口相关参数
        self.ais_shape   = None
        self.topoChecker = TopologyChecker()
        # 文件列表初始化
        self.FileList    = []
        # 默认设置
        self.defaultisSelected = False
        self.defaulttransparency = 0.8
        self.defaultcolor = rgb_color(1,1,1)
        self.defaultfacelistcolor = QtGui.QColor("white")
        # 高亮设置
        self.highlightransparency = 0.0
        self.highlightcolor = rgb_color(0,1,0)
        self.highlightcolor_bot = rgb_color(1,0,0)
        self.highlightfacelistcolor = QtGui.QColor("yellow")
        # 选择项初始化
        self.selected_face_list = list()                 # 选择面数据
        # self.selected_sem_label = list()                 # 选择语义数据
        # self.selected_ins_label = list() 
        # self.selected_bot_label = list() 
        # 索引列表初始化
        self.sem_faces_id = list()                       # 语义对应的面索引
        self.ins_faces_id = list()
        self.bot_faces_id = list() 

    def setupUi(self, LabelModelV0):
        LabelModelV0.setObjectName("LabelModelV0")
        LabelModelV0.setEnabled(True)
        LabelModelV0.resize(800, 545)
        LabelModelV0.setMinimumSize(QtCore.QSize(800, 0))
        LabelModelV0.setSizeIncrement(QtCore.QSize(0, 0))
        LabelModelV0.setTabletTracking(False)
        self.centralwidget = QWidget(LabelModelV0)
        self.centralwidget.setObjectName("centralwidget")
        self.horizontalLayout_2 = QHBoxLayout(self.centralwidget)
        self.horizontalLayout_2.setObjectName("horizontalLayout_2")
        self.verticalLayout_2 = QVBoxLayout()
        self.verticalLayout_2.setObjectName("verticalLayout_2")
        self.verticalLayout_3 = QVBoxLayout()
        self.verticalLayout_3.setObjectName("verticalLayout_3")
        self.formLayout_2 = QFormLayout()
        self.formLayout_2.setObjectName("formLayout_2")

        self.OpenFile = QPushButton(self.centralwidget)
        sizePolicy = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.OpenFile.sizePolicy().hasHeightForWidth())
        self.OpenFile.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setFamily("Microsoft YaHei UI")
        font.setPointSize(10)
        font.setBold(False)
        font.setWeight(50)
        self.OpenFile.setFont(font)
        self.OpenFile.setObjectName("OpenFile")
        self.OpenFile.clicked.connect(self.openFile)
        self.formLayout_2.setWidget(0, QFormLayout.LabelRole, self.OpenFile)

        self.OpenDir = QPushButton(self.centralwidget)
        sizePolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.OpenDir.sizePolicy().hasHeightForWidth())
        self.OpenDir.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setFamily("Microsoft YaHei UI")
        font.setPointSize(10)
        font.setBold(False)
        font.setWeight(50)
        self.OpenDir.setFont(font)
        self.OpenDir.setObjectName("OpenDir")
        self.OpenDir.clicked.connect(self.openDir)
        self.formLayout_2.setWidget(1, QFormLayout.LabelRole, self.OpenDir)

        self.LastFile = QPushButton(self.centralwidget)
        self.LastFile.setEnabled(False)
        sizePolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.LastFile.sizePolicy().hasHeightForWidth())
        self.LastFile.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setFamily("Microsoft YaHei UI")
        font.setPointSize(10)
        self.LastFile.setFont(font)
        self.LastFile.setObjectName("LastFile")
        self.LastFile.clicked.connect(self.lastFile)
        self.formLayout_2.setWidget(0, QFormLayout.FieldRole, self.LastFile)
        
        self.NextFile = QPushButton(self.centralwidget)
        self.NextFile.setEnabled(False)
        sizePolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.NextFile.sizePolicy().hasHeightForWidth())
        self.NextFile.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setFamily("Microsoft YaHei UI")
        font.setPointSize(10)
        self.NextFile.setFont(font)
        self.NextFile.setObjectName("NextFile")
        self.NextFile.clicked.connect(self.nextFile)
        self.formLayout_2.setWidget(1, QFormLayout.FieldRole, self.NextFile)

        self.Clear = QPushButton(self.centralwidget)
        sizePolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.Clear.sizePolicy().hasHeightForWidth())
        self.Clear.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setFamily("Microsoft YaHei UI")
        font.setPointSize(10)
        self.Clear.setFont(font)
        self.Clear.setObjectName("Clear")
        self.Clear.clicked.connect(self.eraseShape)
        self.formLayout_2.setWidget(2, QFormLayout.LabelRole, self.Clear)

        self.Nothing = QPushButton(self.centralwidget)
        self.Nothing.setEnabled(True)
        sizePolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.Nothing.sizePolicy().hasHeightForWidth())
        self.Nothing.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setFamily("Microsoft YaHei UI")
        font.setPointSize(10)
        self.Nothing.setFont(font)
        self.Nothing.setObjectName("Nothing")
        self.Nothing.clicked.connect(self.info)
        self.formLayout_2.setWidget(2, QFormLayout.FieldRole, self.Nothing)
        self.verticalLayout_2.addLayout(self.formLayout_2)

        self.label = QLabel(self.centralwidget)
        sizePolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label.sizePolicy().hasHeightForWidth())
        self.label.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setFamily("Microsoft YaHei UI")
        font.setPointSize(10)
        font.setBold(False)
        font.setWeight(50)
        self.label.setFont(font)
        self.label.setMouseTracking(False)
        self.label.setFrameShape(QFrame.NoFrame)
        self.label.setFrameShadow(QFrame.Plain)
        self.label.setObjectName("label")
        self.verticalLayout_2.addWidget(self.label)

        self.FaceList = QListWidget(self.centralwidget)
        sizePolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.FaceList.sizePolicy().hasHeightForWidth())
        self.FaceList.setSizePolicy(sizePolicy)
        self.FaceList.setObjectName("FaceList")
        self.FaceList.itemClicked.connect(self.faceListClicked)
        self.FaceList.setContextMenuPolicy(Qt.CustomContextMenu)
        self.FaceList.customContextMenuRequested.connect(self.faceListRightClicked)
        self.verticalLayout_2.addWidget(self.FaceList)
        self.horizontalLayout_2.addLayout(self.verticalLayout_2)

        self.canvas = qtDisplay.qtViewer3d(self.centralwidget)
        sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.canvas.sizePolicy().hasHeightForWidth())
        self.canvas.setSizePolicy(sizePolicy)
        self.canvas.setObjectName("Shape")
        self.canvas.InitDriver()
        self.display = self.canvas._display
        self.display.register_select_callback(self.faceClicked)
        # 右键
        self.canvas.setContextMenuPolicy(Qt.CustomContextMenu)
        self.canvas.customContextMenuRequested.connect(self.canvasRightClicked)
        self.horizontalLayout_2.addWidget(self.canvas)

        self.label_2 = QLabel(self.centralwidget)
        sizePolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_2.sizePolicy().hasHeightForWidth())
        self.label_2.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setFamily("Microsoft YaHei UI")
        font.setPointSize(10)
        self.label_2.setFont(font)
        self.label_2.setObjectName("label_2")
        self.verticalLayout_3.addWidget(self.label_2)

        self.SemLabelList = QListWidget(self.centralwidget)
        sizePolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.SemLabelList.sizePolicy().hasHeightForWidth())
        self.SemLabelList.setSizePolicy(sizePolicy)
        self.SemLabelList.setObjectName("SemLabelList")
        # 左键点击高亮
        self.SemLabelList.itemClicked.connect(self.semLabelListClicked)
        # 右键修改删除
        self.SemLabelList.setContextMenuPolicy(Qt.CustomContextMenu)
        self.SemLabelList.customContextMenuRequested.connect(self.semLabelListRightClicked)
        self.verticalLayout_3.addWidget(self.SemLabelList)

        self.label_3 = QLabel(self.centralwidget)
        sizePolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_3.sizePolicy().hasHeightForWidth())
        self.label_3.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setFamily("Microsoft YaHei UI")
        font.setPointSize(10)
        self.label_3.setFont(font)
        self.label_3.setObjectName("label_3")
        self.verticalLayout_3.addWidget(self.label_3)

        # self.InsLabelList = CustomTreeWidget()
        self.InsLabelList = CustomTreeWidget(self.centralwidget)
        sizePolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.InsLabelList.sizePolicy().hasHeightForWidth())
        self.InsLabelList.setSizePolicy(sizePolicy)
        self.InsLabelList.setAutoScrollMargin(16)
        self.InsLabelList.setObjectName("InsLabelList")
        self.InsLabelList.setHeaderHidden(True)
        self.InsLabelList.setItemsExpandable(True)
        # 左键点击高亮
        self.InsLabelList.itemClicked.connect(self.insLabelListClicked) 
        # 右键修改、删除
        self.InsLabelList.setContextMenuPolicy(Qt.CustomContextMenu)
        self.InsLabelList.customContextMenuRequested.connect(self.insLabelListRightClicked)
        # 拖拽
        self.InsLabelList.itemMovedManually.connect(self.handleItemMoved)
        self.verticalLayout_3.addWidget(self.InsLabelList)

        self.label_4 = QLabel(self.centralwidget)
        sizePolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_4.sizePolicy().hasHeightForWidth())
        self.label_4.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setFamily("Microsoft YaHei UI")
        font.setPointSize(10)
        self.label_4.setFont(font)
        self.label_4.setObjectName("label_4")
        self.verticalLayout_3.addWidget(self.label_4)

        self.BotLabelList = QListWidget(self.centralwidget)
        sizePolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.BotLabelList.sizePolicy().hasHeightForWidth())
        self.BotLabelList.setSizePolicy(sizePolicy)
        self.BotLabelList.setObjectName("BotLabelList")
        # 左键点击高亮
        self.BotLabelList.itemClicked.connect(self.botLabelListClicked)
        # 右键修改、删除
        self.BotLabelList.setContextMenuPolicy(Qt.CustomContextMenu)
        self.BotLabelList.customContextMenuRequested.connect(self.botLabelListRightClicked)
        self.verticalLayout_3.addWidget(self.BotLabelList)

        self.label_5 = QLabel(self.centralwidget)
        sizePolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.label_5.sizePolicy().hasHeightForWidth())
        self.label_5.setSizePolicy(sizePolicy)
        font = QtGui.QFont()
        font.setFamily("Microsoft YaHei UI")
        font.setPointSize(10)
        self.label_5.setFont(font)
        self.label_5.setObjectName("label_5")
        self.verticalLayout_3.addWidget(self.label_5)

        self.FileList = QListWidget(self.centralwidget)
        sizePolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.FileList.sizePolicy().hasHeightForWidth())
        self.FileList.setSizePolicy(sizePolicy)
        self.FileList.setObjectName("FileList")
        self.FileList.itemClicked.connect(self.fileListClicked)
        self.verticalLayout_3.addWidget(self.FileList)
        self.horizontalLayout_2.addLayout(self.verticalLayout_3)

        LabelModelV0.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(LabelModelV0)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 800, 23))
        self.menubar.setObjectName("menubar")
        self.menu = QMenu(self.menubar)
        self.menu.setObjectName("menu")
        LabelModelV0.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(LabelModelV0)
        self.statusbar.setObjectName("statusbar")
        LabelModelV0.setStatusBar(self.statusbar)
        self.action1 = QAction(LabelModelV0)
        self.action1.setCheckable(True)
        self.action1.setMenuRole(QAction.ApplicationSpecificRole)
        self.action1.setPriority(QAction.NormalPriority)
        self.action1.setObjectName("action1")
        self.actionda = QAction(LabelModelV0)
        self.actionda.setObjectName("actionda")
        self.actionopen_file = QAction(LabelModelV0)
        self.actionopen_file.setObjectName("actionopen_file")
        self.menu.addAction(self.actionda)
        self.menu.addAction(self.actionopen_file)
        self.menubar.addAction(self.menu.menuAction())

        self.retranslateUi(LabelModelV0)
        QtCore.QMetaObject.connectSlotsByName(LabelModelV0)

        """12. 设置全局快捷键"""
        Shortcut_lastfile = QShortcut(QKeySequence(Qt.Key_A), self.LastFile)
        Shortcut_lastfile.activated.connect(self.lastFile)
        Shortcut_nextfile = QShortcut(QKeySequence(Qt.Key_D), self.NextFile)
        Shortcut_nextfile.activated.connect(self.nextFile)
        Shortcut_clear = QShortcut(QKeySequence(Qt.Key_C), self.Clear)
        Shortcut_clear.activated.connect(self.eraseShape)
        Shortcut_openfile = QShortcut(QKeySequence(Qt.Key_O), self.OpenFile)
        Shortcut_openfile.activated.connect(self.openFile)
        Shortcut_opendir = QShortcut(QKeySequence(Qt.Key_F), self.OpenDir)
        Shortcut_opendir.activated.connect(self.openDir)
        Shortcut_info = QShortcut(QKeySequence(Qt.Key_Q), self.Nothing)
        Shortcut_info.activated.connect(self.info)
        
    def retranslateUi(self, LabelModelV0):
        _translate = QtCore.QCoreApplication.translate
        LabelModelV0.setWindowTitle(_translate("LabelModelV0", "数模标注工具--比亚迪汽车工程研究院AI技术应用部"))
        self.OpenFile.setText(_translate("LabelModelV0", "打开文件"))
        self.LastFile.setText(_translate("LabelModelV0", "上一个"))
        self.OpenDir.setText(_translate("LabelModelV0", "打开文件夹"))
        self.NextFile.setText(_translate("LabelModelV0", "下一个"))
        self.Clear.setText(_translate("LabelModelV0", "清除"))
        self.Nothing.setText(_translate("LabelModelV0", "？"))
        self.label.setText(_translate("LabelModelV0", "几何体列表"))
        self.label_2.setText(_translate("LabelModelV0", "语义标签列表"))
        self.label_3.setText(_translate("LabelModelV0", "实例标签列表"))
        self.label_4.setText(_translate("LabelModelV0", "底面标签列表"))
        self.label_5.setText(_translate("LabelModelV0", "文件列表"))
        self.menu.setTitle(_translate("LabelModelV0", "菜单"))
        self.action1.setText(_translate("LabelModelV0", "1"))
        self.action1.setToolTip(_translate("LabelModelV0", "11"))
        self.actionda.setText(_translate("LabelModelV0", "打开文件"))
        self.actionopen_file.setText(_translate("LabelModelV0", "打开文件夹"))

    """ 1. 打开文件  """
    def openFile(self):
        """
        1. 打开文件 
        """
        self.FileList.clear()
        self.file_name = osp.normpath(QFileDialog.getOpenFileName(self.widget, "打开step文件", "./", "(*.st*p)")[0])
        if self.file_name != ".":
            self.file_dir   = osp.normpath(osp.dirname(str(self.file_name)) if self.file_name else ".")
            self.step_files = glob.glob(f"{self.file_dir}/*.st*p")
            self.file_id  = self.step_files.index(self.file_name)
            for file in self.step_files:
                    self.FileList.addItem(f"{file}")
            self.FileList.item(self.file_id).setSelected(True)
            self.displayAndDataIni()
 
    """ 2. 打开文件夹  """
    def openDir(self):
        """
        2. 打开文件夹，并打开文件夹中的文件，该文件为最近的历史记录或文件夹中第一个文件
        """
        self.FileList.clear()
        self.file_dir = osp.normpath(QFileDialog.getExistingDirectory(self.widget, "打开文件夹")) # 
        if self.file_dir != ".":
            self.step_files = glob.glob(f"{self.file_dir}/*.st*p")
            if len(self.step_files) > 0:
                self.file_name  = self.step_files[0]
                self.file_id  = 0
                # 文件列表窗口
                for file in self.step_files:
                    self.FileList.addItem(f"{file}")
                self.FileList.item(self.file_id).setSelected(True)
                self.displayAndDataIni()

    """得到文件名及文件路径后，进行初始化"""
    def displayAndDataIni(self):
        # 标签文件名
        filename, _     = os.path.splitext(os.path.basename(self.file_name))
        self.label_path = os.path.join(os.path.dirname(self.file_name), filename + "_AAGNet.json")
        # 上一个下一个按钮状态初始化
        self.updateLastAndNext()
        # 数模窗口及面列表窗口初始化
        self.openShape()
        # 标签列表窗口及数据初始化
        if os.path.exists(self.label_path) and os.path.isfile(self.label_path):
            self.loadLabel()
        else:
            self.label_ini()
    
    """标签初始化"""
    def label_ini(self):
        l  = len(self.faces_list)
        self.sem_label = [0]*l
        self.ins_label  = np.zeros((l, l))
        self.bot_label  = [0]*l

    """获取TopoDS_Face类型面的类别"""
    def getfacename(self, face):
        surf_type = BRepAdaptor_Surface(face).GetType()
        if surf_type == GeomAbs_Plane:
            return "GeomAbs_Plane"
        elif surf_type == GeomAbs_Cylinder:
            return "GeomAbs_Cylinder"
        elif surf_type == GeomAbs_Cone:
            return "GeomAbs_Cone"
        elif surf_type == GeomAbs_Sphere:
            return "GeomAbs_Sphere"
        elif surf_type == GeomAbs_Torus:
            return "GeomAbs_Torus"
        elif surf_type == GeomAbs_BezierSurface:
            return "GeomAbs_BezierSurface"
        elif surf_type == GeomAbs_BSplineSurface:
            return "GeomAbs_BSplineSurface"
        elif surf_type == GeomAbs_SurfaceOfRevolution:
            return "GeomAbs_SurfaceOfRevolution"
        elif surf_type == GeomAbs_SurfaceOfExtrusion:
            return "GeomAbs_SurfaceOfExtrusion"
        elif surf_type == GeomAbs_OffsetSurface:
            return "GeomAbs_OffsetSurface"
        elif surf_type == GeomAbs_OtherSurface:
            return "GeomAbs_OtherSurface"
        else:
            errordialog = ErrorInputDialog(f"{self.file_name}出现未知面，请联系开发人员！")
            errordialog.exec_()
            exit(1)
    
    """3. 显示数模  4. 显示面列表序列"""
    def openShape(self):
        """
        3. 显示数模
        4. 显示面列表序列
        """
        if self.file_name is None or self.file_name == '':
            return
        solid = load_body_from_step(self.file_name)
        if not self.topoChecker(solid):
            self.widget.msgBox.warning(self, "warning", "Fail to load, unsupported or wrong STEP.")
            self.file_name = None
            return
        
        self.eraseShape()

        # show the colored shape
        self.ais_shape = AIS_ColoredShape(solid)
        self.display.Context.Display(self.ais_shape, True)
        self.display.FitAll()
        self.display.SetSelectionModeFace()

        #self.display.Context.DisplaySelected(True)
        #self.display.Context.ActivatedModes(self.ais_shape, TColStd_ListOfInteger)
        #self.display.selected_shapes()
        #self.display.Context.Activate()

        # read the faces from shape
        topo = TopologyExplorer(solid)
        self.faces_list = list(topo.faces())

        for fid, face in enumerate(self.faces_list):
            facename = self.getfacename(face)
            self.FaceList.addItem(f"{fid}: {facename}")

    """加载已有标签"""
    def loadLabel(self):
        try:
            with open(self.label_path, 'r', encoding='utf-8') as file:
                label = json.load(file)
                self.sem_label = label["seg"]
                self.ins_label = np.array(label["inst"])
                self.bot_label = label["bottom"]
                # 加载语义标签
                for face_id, sem_label in enumerate(self.sem_label):
                    if sem_label > 0:
                        face_text = self.FaceList.item(face_id).text()
                        self.SemLabelList.addItem(f"{sem_label} {face_text}")
                        self.sem_faces_id += [face_id]
                # 加载实例标签
                face_loaded = []
                for face_id, ins_label_row in enumerate(self.ins_label):
                    faces_id = np.where(ins_label_row == 1)[0].tolist()
                    if faces_id and face_id not in face_loaded:
                        parent_item = QTreeWidgetItem(self.InsLabelList)
                        sem_label = self.sem_label[faces_id[0]]
                        parent_item.setText(0, f"{sem_label}")
                        self.ins_faces_id += [faces_id]
                        for fid in faces_id:
                            face_text = self.FaceList.item(fid).text()
                            child_item  = QTreeWidgetItem(parent_item)
                            child_item.setText(0, f"{face_text}")
                        face_loaded += faces_id
                # 加载底面标签
                for face_id, bot_label in enumerate(self.bot_label): 
                    if bot_label == 1:
                        face_text = self.FaceList.item(face_id).text()
                        sem_label = self.sem_label[face_id]
                        self.BotLabelList.addItem(f"{sem_label} {face_text}")
                        self.bot_faces_id += [face_id]
                if len(self.sem_faces_id) != len(face_loaded) or len(self.ins_faces_id) != len(self.bot_faces_id):
                    errordialog = ErrorInputDialog(f"加载失败！{self.label_path}数据错误！将初始化标签")
                    errordialog.exec_()
                    self.label_ini()
                    self.SemLabelList.clear()                        # 语义标签窗口
                    self.InsLabelList.clear()
                    self.BotLabelList.clear()
                    self.sem_faces_id.clear()
                    self.ins_faces_id.clear()
                    self.bot_faces_id.clear()
                    self.savelabel()
        except json.JSONDecodeError:
            errordialog = ErrorInputDialog(f"加载失败！{self.label_path}为非法的json文件")
            errordialog.exec_()
        except Exception as e:
            errordialog = ErrorInputDialog(f"加载失败！加载{self.label_path}时发生错误：{e}")
            errordialog.exec_()
        
    """设置面颜色及透明度"""
    def setFaceColorAndTransparency(self, face, color, transparency):
        self.ais_shape.SetCustomColor(face, color)
        self.ais_shape.SetCustomTransparency(face, transparency)

    """设置faces列表中面颜色、透明度，及其在面列表、标签列表中的背景颜色、是否选中"""
    def setListAndShape(self, faces, isSelected):
        # 设置数模面以及面列表
        if isSelected:
            color = self.highlightcolor
            color_bot = self.highlightcolor_bot
            transparency = self.highlightransparency
            facelistcolor = self.highlightfacelistcolor
        else:
            color = self.defaultcolor
            color_bot = self.defaultcolor
            transparency = self.defaulttransparency
            facelistcolor = self.defaultfacelistcolor
        for face in faces:
            self.setFaceColorAndTransparency(face, color, transparency)
            face_id = self.faces_list.index(face)
            self.FaceList.item(face_id).setBackground(facelistcolor)
            self.FaceList.item(face_id).setSelected(isSelected)
            if face_id in self.sem_faces_id:
                SemLabelList_id = self.sem_faces_id.index(face_id)
                self.SemLabelList.item(SemLabelList_id).setBackground(facelistcolor)
                self.SemLabelList.item(SemLabelList_id).setSelected(isSelected)
            for ins_face_id in self.ins_faces_id:
                if face_id in ins_face_id:
                    InsLabelList_pid = self.ins_faces_id.index(ins_face_id)
                    InsLabelList_cid = ins_face_id.index(face_id)
                    parent_item = self.InsLabelList.topLevelItem(InsLabelList_pid)
                    child_item = parent_item.child(InsLabelList_cid)
                    parent_item.setBackground(0, facelistcolor)
                    parent_item.setSelected(isSelected)
                    child_item.setBackground(0, facelistcolor)
                    child_item.setSelected(isSelected)
            if face_id in self.bot_faces_id:
                self.setFaceColorAndTransparency(face, color_bot, transparency)
                BotLabelList_id = self.bot_faces_id.index(face_id)
                self.BotLabelList.item(BotLabelList_id).setBackground(facelistcolor)
                self.BotLabelList.item(BotLabelList_id).setSelected(isSelected)
    
    """数模、面列表及标签列表恢复默认状态""" 
    def defaultListAndShape(self):
        if self.selected_face_list:
            # 选择面恢复
            self.setListAndShape(self.selected_face_list, self.defaultisSelected)
        else:
            # 所有面为初始状态，更新为透明状态
            for face in self.faces_list:
                self.setFaceColorAndTransparency(face, self.defaultcolor,
                                                 self.defaulttransparency)
        self.selected_face_list = []
    
    """5. 1) 单击数模选中面"""
    def faceClicked(self, shp, *kwargs):
        """
        5. 选中面
            1) 单击数模选中
        """
        if self.ais_shape and self.file_name and self.faces_list and shp:
            self.defaultListAndShape()
            # 高亮选中的面，高亮面对应的面序列
            self.setListAndShape(shp, True)
            # 数模显示
            self.display.Context.Display(self.ais_shape, True)
            self.selected_face_list = shp

    """5. 2) 单击面序列选中面"""
    def faceListClicked(self):
        """
        5. 选中面
            2) 单击面序列选中
        """
        if self.ais_shape and self.file_name and self.faces_list:
            selected_row  = self.FaceList.currentRow()
            selected_face = self.faces_list[selected_row]
            self.defaultListAndShape()
            self.setListAndShape([selected_face], True)
            self.display.Context.Display(self.ais_shape, True)
            self.selected_face_list = [selected_face]

    """新增语义(仅)打标，不考虑是否已有。由于标签为向量，一个面最多对应一个特征""" 
    def addSemLabel(self, face_id, sem_label, face_text):
        self.sem_label[face_id] = int(sem_label)
        self.SemLabelList.addItem(f"{sem_label} {face_text}")
        self.sem_faces_id += [face_id]
    
    """调整语义(仅)标签，不考虑是否已有"""
    def modifySemLabel(self, face_id, sem_label, face_text):
        self.sem_label[face_id] = int(sem_label)
        SemLabelList_id = self.sem_faces_id.index(face_id)
        self.SemLabelList.item(SemLabelList_id).setText(f"{sem_label} {face_text}")

    """删除语义(仅)标签"""
    def deleteSemLabel(self, SemLabelList_id):
        self.SemLabelList.takeItem(SemLabelList_id)
        face_id = self.sem_faces_id.pop(SemLabelList_id)
        self.sem_label[face_id] = 0

    """新增单个实例(仅)标签，不考虑是否已有"""
    def addInsLabel(self, face_id, sem_label, face_text):
        parent_item = QTreeWidgetItem(self.InsLabelList)
        parent_item.setText(0, f"{sem_label}")
        self.ins_faces_id += [[face_id]]
        child_item = QTreeWidgetItem(parent_item)
        child_item.setText(0, f"{face_text}")
        self.ins_label[face_id, face_id] = 1

    """删除实例标签，并调整底面"""
    def deleteInsChildLabel(self, face_id):
        # 删除子项，更新列表、更新self.ins_faces_id及标签
        # 1. 若父项仅有该子项，则删除父项及对应底面标注
        # 2. 若父项有多个子项，则删除子项即可
        # 3. 若父项有多个子项，且该子项为底面，则必为父项对应底面，需调整父项底面
        for ins_face_id in self.ins_faces_id:
            if face_id in ins_face_id:
                InsLabelList_pid = self.ins_faces_id.index(ins_face_id)
                InsLabelList_cid = ins_face_id.index(face_id)
                parent_item = self.InsLabelList.topLevelItem(InsLabelList_pid)
                child_item = parent_item.child(InsLabelList_cid)
                parent_item.removeChild(child_item)
                self.ins_faces_id[InsLabelList_pid].pop(InsLabelList_cid)
                if parent_item.childCount() == 0:
                    self.InsLabelList.takeTopLevelItem(InsLabelList_pid)
                    self.ins_faces_id.pop(InsLabelList_pid)
                    # 删除对应的底面标签
                    self.deleteBotLabel(InsLabelList_pid)
                self.ins_label[face_id, :] = 0
                self.ins_label[:, face_id] = 0
                if face_id in self.bot_faces_id:
                    self.modifyBotLabelListItem(self.BotLabelList.item(InsLabelList_pid))
            
    """新增底面(仅)标签，不考虑是否已有"""
    def addBotLabel(self, face_id, sem_label, face_text):
        self.bot_label[face_id] = 1
        self.BotLabelList.addItem(f"{sem_label} {face_text}")
        self.bot_faces_id += [face_id]

    """调整底面标签对应的语义标签，不考虑是否已有"""
    def modifyBotLabel(self, face_id, sem_label, face_text):
        BotLabelList_id = self.bot_faces_id.index(face_id)
        face_text = self.FaceList.item(face_id).text()
        self.BotLabelList.item(BotLabelList_id).setText(f"{sem_label} {face_text}")

    """删除底面标签，不考虑是否已有"""
    def deleteBotLabel(self, BotLabelList_id):
        self.BotLabelList.takeItem(BotLabelList_id)
        face_id = self.bot_faces_id.pop(BotLabelList_id)
        self.bot_label[face_id] = 0

    """√ 仅对一个面打标，考虑所有情况"""
    def addLabel(self, face_id, sem_label, face_text):
        """√ 仅对一个面打标，考虑所有情况
        注：语义面和实例面一一对应，底面一定在语义面中，一个底面对应一个实例
        1. 若以语义打标：语义标签无变化，则无变化，变化则调整所有标签
        2. 若未语义打标：新增所有标签
        """
        if face_id in self.sem_faces_id:                                # 2
            # face_id已有对应语义、实例标签，标签无变化
            if self.sem_label[face_id] == int(sem_label):
                return
            else:
                # 调整语义标签
                self.modifySemLabel(face_id, sem_label, face_text)
                # 调整实例标签，先删除后增加
                self.deleteInsChildLabel(face_id)
                self.addInsLabel(face_id, sem_label, face_text)
                # 调整底面标签
                self.addBotLabel(face_id, sem_label, face_text)           
        else:                                                             # 3
            # face_id未标注
            self.addSemLabel(face_id, sem_label, face_text)
            self.addInsLabel(face_id, sem_label, face_text)
            self.addBotLabel(face_id, sem_label, face_text)
        self.savelabel()

    """√ 同时对多个面打标，这些面均放在一个实例中"""
    def addLabels(self, face_id, sem_label, dialog_text):
        confirmBotLabel = BotLabelInputDialog(dialog_text, face_id)
        if confirmBotLabel.exec_() == QDialog.Accepted:
            fid = confirmBotLabel.getBotLabelInput()
            self.addBotLabel(fid, sem_label, self.FaceList.item(fid).text())
        # 1. 若已整体被打标为一个实例标签
        if face_id in self.ins_faces_id:
            InsLabelList_pid = self.ins_faces_id.index(face_id)
            parent_item = self.InsLabelList.topLevelItem(InsLabelList_pid)
            if parent_item.text(0) == sem_label:
                # 若语义标签无变化，则返回
                self.savelabel()
                return
            else:
                # 若语义标签改变，则修改父项名，并修改语义标签
                parent_item.setText(0, f"{sem_label}")
                for fid in face_id:
                    ftxt = self.FaceList.item(fid).text()
                    self.modifySemLabel(fid, sem_label, ftxt)
        # 2. 若未整体被打标为一个实例标签，则打标为一个实例，调整语义和底面
        else:
            parent_item = QTreeWidgetItem(self.InsLabelList)
            parent_item.setText(0, f"{sem_label}")
            for fid in face_id:
                ftxt = self.FaceList.item(fid).text()
                # 语义标签
                if fid in self.sem_faces_id:
                    self.modifySemLabel(fid, sem_label, ftxt)
                else:
                    self.addSemLabel(fid, sem_label, ftxt)
                # 实例标签
                if self.ins_faces_id:
                    self.deleteInsChildLabel(fid)
                child_item = QTreeWidgetItem(parent_item)
                child_item.setText(0, f"{ftxt}")
                for fidi in face_id:
                    self.ins_label[fid, fidi] = 1
            self.ins_faces_id += [face_id]
        self.savelabel()

    """√ 通过弹窗获得语义标签后，同时对多个面打标，这些面均放在一个实例中"""
    def dialog2Labels(self, faces_id, dialog_text):
        dialog = CustomInputDialog(dialog_text)
        if dialog.exec_() == QDialog.Accepted:
            sem_label = dialog.getTextInput()
            try:
                self.addLabels(faces_id, sem_label, dialog_text)
            except ValueError:
                errordialog = ErrorInputDialog(f"{sem_label}无法转为整型！")
                errordialog.exec_()

    """6. 1) 面序列右键标注面"""
    def faceListRightClicked(self, pos):
        """
        6. 标注面，右键弹出标记为，或者双击？
            1) 面序列右键
        """
        index = self.FaceList.indexAt(pos)
        if index.isValid():
            # 直接打开对话框
            face_text = self.FaceList.itemFromIndex(index).text()
            dialog = CustomInputDialog(face_text)
            if dialog.exec_() == QDialog.Accepted:
                sem_label = dialog.getTextInput()
                print(f"{self.FaceList.currentRow()} {face_text} {sem_label}")
                face_id = index.row()
                try:
                    self.addLabel(face_id, sem_label, face_text)
                except ValueError:
                    errordialog = ErrorInputDialog(f"{sem_label}无法转为整型！")
                    errordialog.exec_()
                    self.faceListRightClicked(pos)

    """6. 2) 数模右键标注面"""
    def canvasRightClicked(self):
        if not self.selected_face_list:
            return
        faces_id = []
        dialog_text = ""
        for selected_face in self.selected_face_list:
            face_id = self.faces_list.index(selected_face)
            face_text = self.FaceList.item(face_id).text()
            faces_id += [face_id]
            dialog_text += f"{face_text}\n"
        self.dialog2Labels(faces_id, dialog_text)

    """7. 1) 左键单击标签，标签高亮，且关联面列表及数模展示窗口，面高亮时，对应标签高亮"""
    def semLabelListClicked(self):
        """
        7. 显示语义标签
            1) 左键单击语义标签，标签高亮，且关联面列表及数模展示窗口，面高亮时，对应标签高亮
        """
        if self.ais_shape and self.file_name and self.sem_faces_id:
            SemLabelList_id  = self.SemLabelList.currentRow()
            selected_face = self.faces_list[self.sem_faces_id[SemLabelList_id]]
            self.defaultListAndShape()
            self.setListAndShape([selected_face], True)
            self.display.Context.Display(self.ais_shape, True)
            self.selected_face_list = [selected_face]
        
    def insLabelListClicked(self, item, column):
        """
        7. 显示实例标签
            1) 左键单击实例标签，标签高亮，且关联面列表及数模展示窗口，面高亮时，对应标签高亮
        """
        parent = item.parent()
        if parent:
            InsLabelList_pid = self.InsLabelList.indexOfTopLevelItem(parent)
            InsLabelList_cid = parent.indexOfChild(item)
            selected_face = [self.faces_list[self.ins_faces_id[InsLabelList_pid][InsLabelList_cid]]]
        else:
            InsLabelList_pid = self.InsLabelList.indexOfTopLevelItem(item)
            selected_face = [self.faces_list[face_id] for face_id in self.ins_faces_id[InsLabelList_pid]]
        self.defaultListAndShape()
        self.setListAndShape(selected_face, True)
        self.display.Context.Display(self.ais_shape, True)
        self.selected_face_list = selected_face
    
    def botLabelListClicked(self):
        """
        7. 显示底面标签
            1) 左键单击底面标签，且关联面列表及数模展示窗口，面高亮时，对应标签高亮
        """
        if self.ais_shape and self.file_name and self.bot_faces_id:
            BotLabelList_id  = self.BotLabelList.currentRow()
            selected_face = self.faces_list[self.bot_faces_id[BotLabelList_id]]
            self.defaultListAndShape()
            self.setListAndShape([selected_face], True)
            self.display.Context.Display(self.ais_shape, True)
            self.selected_face_list = [selected_face]

    """语义标签列表右键之修改标签"""
    def modifySemLabelListItem(self, item):
        SemLabelList_id = self.SemLabelList.row(item)
        face_id = self.sem_faces_id[SemLabelList_id]
        face_text = self.FaceList.item(face_id).text()
        dialog = CustomInputDialog(face_text)
        if dialog.exec_() == QDialog.Accepted:
            sem_label = dialog.getTextInput()
            try:
                self.sem_label[face_id] = int(sem_label)
                self.SemLabelList.item(SemLabelList_id).setText(f"{sem_label} {face_text}")
                self.deleteInsChildLabel(face_id) # 底面与实例一一对应
                self.addInsLabel(face_id, sem_label, face_text)
                self.addBotLabel(face_id, sem_label, face_text)
                self.savelabel()
            except ValueError:
                errordialog = ErrorInputDialog(ValueError)
                errordialog.exec_()
                self.modifySemLabelListItem(item)
                
    """语义标签列表右键之删除标签"""
    def deleteSemLabelListItem(self, item):
        # 删除选中的item
        SemLabelList_id = self.SemLabelList.row(item)
        self.SemLabelList.takeItem(SemLabelList_id)
        face_id = self.sem_faces_id.pop(SemLabelList_id)
        self.sem_label[face_id] = 0
        self.deleteInsChildLabel(face_id)
        self.savelabel()

    """实例标签列表右键之修改标签"""
    def modifyInsLabelListItem(self, item):
        """
        如果是父项，修改sem_label，对应子面的语义、实例以及底面
        如果是子项，修改sem_label，对应面的语义、实例以及底面
        """
        parent = item.parent()
        if parent: # 子项
            InsLabelList_pid = self.InsLabelList.indexOfTopLevelItem(parent)
            InsLabelList_cid = parent.indexOfChild(item)
            face_id = self.ins_faces_id[InsLabelList_pid][InsLabelList_cid]
            face_text = self.FaceList.item(face_id).text()
            dialog = CustomInputDialog(face_text)
            if dialog.exec_() == QDialog.Accepted:
                sem_label = dialog.getTextInput()
                try:
                    self.sem_label[face_id] = int(sem_label)
                    SemLabelList_id = self.sem_faces_id.index(face_id)
                    self.SemLabelList.item(SemLabelList_id).setText(f"{sem_label} {face_text}")
                    self.deleteInsChildLabel(face_id)
                    self.addInsLabel(face_id, sem_label, face_text)
                    self.addBotLabel(face_id, sem_label, face_text)
                    self.savelabel()
                except ValueError:
                    errordialog = ErrorInputDialog(ValueError)
                    errordialog.exec_()
        else:      # 父项
            InsLabelList_pid  = self.InsLabelList.indexOfTopLevelItem(item)
            face_id = self.ins_faces_id[InsLabelList_pid]
            dialog_text = ""
            for fid in face_id:
                dialog_text += f"{self.FaceList.item(fid).text()}\n" 
            self.dialog2Labels(face_id, dialog_text)
                
    """实例标签列表右键之删除标签"""
    def deleteInsLabelListItem(self, item):
        """
        如果是父项，删除所有子面对应的语义、实例以及底面
        如果是子项，删除子面对应的语义、实例以及底面
        """
        parent = item.parent()
        if parent: # 子项
            # 实例
            InsLabelList_pid = self.InsLabelList.indexOfTopLevelItem(parent)
            InsLabelList_cid = parent.indexOfChild(item)
            face_id = self.ins_faces_id[InsLabelList_pid][InsLabelList_cid]
            parent_item = self.InsLabelList.topLevelItem(InsLabelList_pid)
            child_item = parent_item.child(InsLabelList_cid)
            parent_item.removeChild(child_item)
            self.ins_faces_id[InsLabelList_pid].pop(InsLabelList_cid)
            if parent_item.childCount() == 0:
                self.InsLabelList.takeTopLevelItem(InsLabelList_pid)
                self.ins_faces_id.pop(InsLabelList_pid)
            self.ins_label[face_id, :] = 0
            self.ins_label[:, face_id] = 0
            # 语义
            self.deleteSemLabel(self.sem_faces_id.index(face_id))
            # 底面
            if face_id in self.bot_faces_id:
                self.deleteBotLabel(self.bot_faces_id.index(face_id))
        else:      # 父项
            # 实例
            InsLabelList_pid = self.InsLabelList.indexOfTopLevelItem(item)
            face_id = self.ins_faces_id[InsLabelList_pid]
            self.InsLabelList.takeTopLevelItem(InsLabelList_pid)
            self.ins_faces_id.pop(InsLabelList_pid)
            # 底面 
            self.deleteBotLabel(InsLabelList_pid)
            for fid in face_id:
                self.ins_label[fid, :] = 0
                self.ins_label[:, fid] = 0
                # 语义
                self.deleteSemLabel(self.sem_faces_id.index(fid))

        self.savelabel()

    """底面标签列表右键之修改标签，修改底面对应的面"""
    def modifyBotLabelListItem(self, item):
        """
        修改底面对应的面,仅调整底面标签self.bot_label、self.bot_faces_id、self.BotLabelList
        """
        BotLabelList_id = self.BotLabelList.row(item)
        # 弹窗
        faces_id = self.ins_faces_id[BotLabelList_id]
        dialog_text = ""
        for face_id in faces_id:
            face_text = self.FaceList.item(face_id).text()
            dialog_text += f"{face_text}\n"
        confirmBotLabel = BotLabelInputDialog(dialog_text, faces_id)
        if confirmBotLabel.exec_() == QDialog.Accepted:
            fid = confirmBotLabel.getBotLabelInput()
            # 列表 标签 面id
            self.bot_label[self.bot_faces_id[BotLabelList_id]] = 0
            self.bot_faces_id[BotLabelList_id] = fid
            sem_label = self.sem_label[fid]
            face_text = self.FaceList.item(fid).text()
            self.BotLabelList.item(BotLabelList_id).setText(f"{sem_label} {face_text}")
            self.bot_label[fid] = 1
            self.savelabel()
        else:
            self.modifyBotLabelListItem(item)
                
    """底面标签列表右键之删除标签，同时删除底面对应特征的所有面语义、实例标签"""
    def deleteBotLabelListItem(self, item):
        """
        删除选中的底面
        1. 删除底面
        2. 删除底面对应特征的所有面语义、实例标签
        """
        # 1. 删除底面
        BotLabelList_id = self.BotLabelList.row(item)
        self.BotLabelList.takeItem(BotLabelList_id)
        face_id = self.bot_faces_id.pop(BotLabelList_id)
        self.bot_label[face_id] = 0
        # 2. 删除faces_id中所有面对应的语义标签
        faces_id = self.ins_faces_id[BotLabelList_id]
        for face_id in faces_id:
            self.deleteSemLabel(self.sem_faces_id.index(face_id))
            self.ins_label[face_id, :] = 0
            self.ins_label[:, face_id] = 0
        # 2. 删除faces_id中所有面对应的实例标签，ins_faces_id、InsLabelList、ins_label
        self.ins_faces_id.pop(BotLabelList_id)
        self.InsLabelList.takeTopLevelItem(BotLabelList_id)
        self.savelabel()

    """7. 2) 显示标签，右键菜单，包括修改及删除"""
    def semLabelListRightClicked(self, pos):
        """
        7. 显示标签
            2) 右键菜单，包括修改及删除
        """
        item = self.SemLabelList.itemAt(pos)
        if item:
            contextMenu = QMenu(self.widget)
            # 添加动作
            createAction = QAction("1. 修改")
            createAction.triggered.connect(lambda: self.modifySemLabelListItem(item))
            deleteAction = QAction("2. 删除")
            deleteAction.triggered.connect(lambda: self.deleteSemLabelListItem(item))
            contextMenu.addAction(createAction)           
            contextMenu.addAction(deleteAction)
            # 在鼠标位置显示菜单
            contextMenu.exec_(self.SemLabelList.mapToGlobal(pos))

    def insLabelListRightClicked(self, pos):
        """
        7. 显示标签
            2) 右键菜单，包括修改及删除
        """
        item = self.InsLabelList.itemAt(pos)
        if item:
            contextMenu = QMenu(self.widget)
            # 添加动作
            createAction = QAction("1. 修改")
            createAction.triggered.connect(lambda: self.modifyInsLabelListItem(item))
            deleteAction = QAction("2. 删除")
            deleteAction.triggered.connect(lambda: self.deleteInsLabelListItem(item))
            contextMenu.addAction(createAction)           
            contextMenu.addAction(deleteAction)
            # 在鼠标位置显示菜单
            contextMenu.exec_(self.InsLabelList.mapToGlobal(pos))
    
    def botLabelListRightClicked(self, pos):
        """
        7. 显示标签
            2) 右键菜单，包括修改及删除
        """
        item = self.BotLabelList.itemAt(pos)
        if item:
            contextMenu = QMenu(self.widget)
            # 添加动作
            createAction = QAction("1. 修改")
            createAction.triggered.connect(lambda: self.modifyBotLabelListItem(item))
            deleteAction = QAction("2. 删除")
            deleteAction.triggered.connect(lambda: self.deleteBotLabelListItem(item))
            contextMenu.addAction(createAction)           
            contextMenu.addAction(deleteAction)
            # 在鼠标位置显示菜单
            contextMenu.exec_(self.BotLabelList.mapToGlobal(pos))
    
    """实例标签左键拖拽功能"""
    def handleItemMoved(self, soure_item, dest_parent):
        # 如果dest_parent非空，则新建实例子项，修改语义，删除源项，如果源项为底面且原父项非空，则重选底面
        # 否则，则删除源项，如果源项为底面，则重选底面，新增父项，新增语义、底面
        # 获得源face_text、face_id
        soure_parent = soure_item.parent()
        InsLabelList_pid = self.InsLabelList.indexOfTopLevelItem(soure_parent)
        InsLabelList_cid = soure_parent.indexOfChild(soure_item)
        InsLabelList_did = self.InsLabelList.indexOfTopLevelItem(dest_parent)
        face_id = self.ins_faces_id[InsLabelList_pid][InsLabelList_cid]
        face_text = self.FaceList.item(face_id).text()
        if not dest_parent.parent():  # 目标项为父项，即拖动至非空区域
            # 新建实例子项，修改语义，目标实例已有底面，不需要操作
            sem_label = int(dest_parent.text(0))
            child_item = QTreeWidgetItem(dest_parent)
            child_item.setText(0, f"{face_text}")
            self.ins_faces_id[InsLabelList_did] += [face_id]
            dest_pid = self.InsLabelList.indexOfTopLevelItem(dest_parent)
            dest_faces_id = self.ins_faces_id[dest_pid]
            self.ins_label[face_id, :] = 0
            self.ins_label[:, face_id] = 0
            for fid in dest_faces_id:
                self.ins_label[fid, face_id] = 1
                self.ins_label[face_id, fid] = 1
            self.modifySemLabel(face_id, sem_label, face_text)
            # 删除原子项
            soure_parent.removeChild(soure_item)
            self.ins_faces_id[InsLabelList_pid].pop(InsLabelList_cid)
            if soure_parent.childCount() == 0: # 原父项为空，face_id必为底面
                self.InsLabelList.takeTopLevelItem(InsLabelList_pid)
                self.ins_faces_id.pop(InsLabelList_pid)
                self.deleteBotLabel(InsLabelList_pid)
            if face_id in self.bot_faces_id: # 若在底面，原父项非空，弹出窗口，原父项重选窗口
                self.modifyBotLabelListItem(self.BotLabelList.item(InsLabelList_pid))
        else:
            # 目标项为非父项，即拖动至空区域
            # 新建父项，新增语义、底面
            dialog = CustomInputDialog(face_text)
            if dialog.exec_() == QDialog.Accepted:
                sem_label = dialog.getTextInput()
                try:
                    self.modifySemLabel(face_id, sem_label, face_text)
                    self.deleteInsChildLabel(face_id)
                    parent_item = QTreeWidgetItem(self.InsLabelList)
                    parent_item.setText(0, f"{sem_label}")
                    self.ins_faces_id += [[face_id]]
                    child_item = QTreeWidgetItem(parent_item)
                    child_item.setText(0, f"{face_text}")
                    self.ins_label[face_id, face_id] = 1
                    self.addBotLabel(face_id, sem_label, face_text)
                except ValueError:
                    errordialog = ErrorInputDialog(f"{sem_label}无法转为整型！")
                    errordialog.exec_()
        self.savelabel()

    """实例标签左键拖拽功能
    def handleItemMoved(self, soure_item, dest_parent, dest_item):
        # 如果dest_parent非空，则新建实例子项，修改语义，删除源项，如果源项为底面且原父项非空，则重选底面
        # 否则，则删除源项，如果源项为底面，则重选底面，新增父项，新增语义、底面
        # 获得源face_text、face_id
        soure_parent = soure_item.parent()
        InsLabelList_pid = self.InsLabelList.indexOfTopLevelItem(soure_parent)
        InsLabelList_cid = soure_parent.indexOfChild(soure_item)
        face_id = self.ins_faces_id[InsLabelList_pid][InsLabelList_cid]
        face_text = self.FaceList.item(face_id).text()

        if not dest_parent.parent():  # 目标项为父项，即拖动至非空区域
            # 新建实例子项，修改语义，目标实例已有底面，不需要操作
            sem_label = int(dest_parent.text(0))
            # dest_parent.addChild(soure_item)
            child_item = QTreeWidgetItem(dest_parent)
            child_item.setText(0, f"{face_text}")
            dest_pid = self.InsLabelList.indexOfTopLevelItem(dest_parent)
            dest_faces_id = self.ins_faces_id[dest_pid]
            self.ins_label[face_id, :] = 0
            self.ins_label[:, face_id] = 0
            for fid in dest_faces_id:
                self.ins_label[fid, face_id] = 1
                self.ins_label[face_id, fid] = 1
            self.modifySemLabel(face_id, sem_label, face_text)
            # 删除原子项
            soure_parent.removeChild(soure_item)
            self.ins_faces_id[InsLabelList_pid].pop(InsLabelList_cid)
            if soure_parent.childCount() == 0: # 原父项为空，face_id必为底面
                self.InsLabelList.takeTopLevelItem(InsLabelList_pid)
                self.ins_faces_id.pop(InsLabelList_pid)
                self.deleteBotLabel(InsLabelList_pid)
            if face_id in self.bot_faces_id: # 若在底面，原父项非空，弹出窗口，原父项重选窗口
                self.modifyBotLabelListItem(self.BotLabelList.item(InsLabelList_pid))
            # 消除默认拖动影响
            if dest_item.parent():
                # 拖至子项：source_item、dest_parent、dest_parent，删除新增子项
                dest_item.removeChild(soure_item)
            else:
                # 拖至主项：source_item、dest_parent、dest_item，删除子项的子项
                dest_parent.removeChild(soure_item)
        else:
            # 目标项为非父项，即拖动至空区域
            # 新建父项，新增语义、底面
            dialog = CustomInputDialog(face_text)
            if dialog.exec_() == QDialog.Accepted:
                sem_label = dialog.getTextInput()
                try:
                    self.modifySemLabel(face_id, sem_label, face_text)
                    self.deleteInsChildLabel(face_id)
                    parent_item = QTreeWidgetItem(self.InsLabelList)
                    parent_item.setText(0, f"{sem_label}")
                    self.ins_faces_id += [[face_id]]
                    parent_item.addChild(soure_item)
                    self.ins_label[face_id, face_id] = 1
                    self.addBotLabel(face_id, sem_label, face_text)
                except ValueError:
                    errordialog = ErrorInputDialog(f"{sem_label}无法转为整型！")
                    errordialog.exec_()
            # 消除默认拖动影响，拖至空白区域，默认拖动会新增项，删除新增主项
            err_pid = self.InsLabelList.indexOfTopLevelItem(soure_item)
            self.InsLabelList.takeTopLevelItem(err_pid)
    """

    """ 更新上一个、下一个按键状态  """
    def updateLastAndNext(self):
        if len(self.step_files) == 1:
            self.NextFile.setDisabled(True)
            self.LastFile.setDisabled(True)
        else:
            if self.file_id == 0:
                # 上一个置灰，下一个激活
                self.NextFile.setEnabled(True)
                self.LastFile.setDisabled(True)
            elif self.file_id == len(self.step_files)-1:
                # 下一个置灰，上一个激活
                self.NextFile.setDisabled(True)
                self.LastFile.setEnabled(True)
            else :
                self.NextFile.setEnabled(True)
                self.LastFile.setEnabled(True)
    """8. 上一个"""
    def lastFile(self):
        """
        8. 上一个
        """
        self.file_id = self.file_id-1
        self.file_name = self.step_files[self.file_id]
        self.displayAndDataIni()
        # FileList状态更新
        self.FileList.item(self.file_id).setSelected(True)

    """9. 下一个"""
    def nextFile(self):
        """
        9. 下一个
        """
        self.file_id = self.file_id+1
        self.file_name = self.step_files[self.file_id]
        self.displayAndDataIni()
        # FileList状态更新
        self.FileList.item(self.file_id).setSelected(True)

    """10. 保存标注结果"""        
    def savelabel(self):
        """
        10. 保存标注结果
        """
        label = {"seg": self.sem_label, "inst": self.ins_label.tolist(),
                 "bottom": self.bot_label}
        with open(self.label_path, 'w') as json_file:
            json.dump(label, json_file, indent=4, ensure_ascii=False, sort_keys=False)
        print(f'标签保存到：{self.label_path}')

    """11. 清除数模及数据"""
    def eraseShape(self):
        """
        11. 清除数模及数据
        """
        if self.ais_shape:
            self.display.Context.Erase(self.ais_shape, True) # 数模窗口
            self.ais_shape = None                            # 数模数据
            self.FaceList.clear()                            # 面列表窗口
            self.faces_list.clear()                          # 面列表数据
            self.selected_face_list.clear()                  # 选择面数据
            self.SemLabelList.clear()                        # 语义标签窗口
            self.InsLabelList.clear()
            self.BotLabelList.clear()
            # self.selected_ins_label.clear()                  # 选择实例数据
            # self.selected_sem_label.clear()
            # self.selected_bot_label.clear()
            self.sem_faces_id.clear()
            self.ins_faces_id.clear()
            self.bot_faces_id.clear()

    """12. 快捷键"""
    """见504"""

    """13. 文件列表，单击选中打开文件"""
    def fileListClicked(self):
        self.file_id = self.FileList.currentRow()
        self.file_name = self.step_files[self.file_id]
        self.displayAndDataIni()

    """?按键"""
    def info(self):
        intro0 = "说明：\n    1. 一个面仅限一个语义标签！\n    2. 一个实例标签可以包括多个面！\n"
        intro1 = "    3. 打了语义标签的面和所有打了实例标签的面是一一对应的！\n    4. 实例标签和底面标签一一对应\n"
        intro2 = "    5. 数模窗口可选择多个面打标\n    6. 实例标签窗口支持拖拽\n"
        infomation = "\n快捷键：\n    o：打开文件\n    f：打开文件夹\n    c：清除\n    a：上一个\n    d：下一个\n    q：？"
        infodialog = ErrorInputDialog(intro0 + intro1 + intro2 + infomation)
        infodialog.initUI(infomation, title = "说明及快捷键")
        infodialog.exec_()

if __name__ == "__main__":
    translator = QtCore.QTranslator()
    translator.load(
        QtCore.QLocale.system().name(),
        osp.dirname(osp.abspath(__file__)) + "/translate",
        )
    app = QApplication(sys.argv)
    app.setApplicationName("数模标注工具--比亚迪汽车工程研究院AI技术应用部")
    app.installTranslator(translator)
    ex = LabelShapeV0()
    mw = QMainWindow()
    ex.setupUi(mw)
    mw.show()
    
    if os.getenv("APPVEYOR") is None:
        sys.exit(app.exec_())