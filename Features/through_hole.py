import random
import math
import numpy as np
from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakePrism
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire, BRepBuilderAPI_MakeFace
from OCC.Core.gp import gp_Circ, gp_Ax2, gp_Pnt, gp_Dir
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
import Utils.occ_utils as occ_utils
from Features.machining_features import MachiningFeature
from OCC.Core.GProp import GProp_GProps
from OCC.Core.BRepGProp import brepgprop_SurfaceProperties
from OCC.Core.BRepAdaptor import BRepAdaptor_Surface
from OCC.Core.STEPControl import STEPControl_Writer, STEPControl_AsIs,STEPControl_Reader
def write_step_wth_prediction(filename, shape):
    writer = STEPControl_Writer()
    writer.Transfer(shape, STEPControl_AsIs)

    writer.Write(filename)

class ThroughHole(MachiningFeature):
    def __init__(self, shape, label_map, min_len, clearance, feat_names):
        super().__init__(shape, label_map, min_len, clearance, feat_names)
        self.shifter_type = 4
        self.bound_type = 4
        self.depth_type = "through"
        self.feat_type = "through_hole"



    def _add_sketch(self, bound):
        dir_w = bound[2] - bound[1]
        dir_h = bound[0] - bound[1]
        width = np.linalg.norm(dir_w)
        height = np.linalg.norm(dir_h)
        dir_w = dir_w / width
        dir_h = dir_h / height
        normal = np.cross(dir_w, dir_h)

        radius = min(width / 2, height / 2)

        center = (bound[0] + bound[1] + bound[2] + bound[3]) / 4
        info = center.tolist()
    

        # my_list = [1,2,3,5,7,14,16]
        my_list = [26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41]
        rv = random.choice(my_list) 

        if rv == 26:
            luo_rad = (-131.62278992, 499.21603534, 213.33373081 )
            r = 6
            d_r = 13
        elif rv == 27:
            luo_rad = (-163.21153959, 490.62807964, 136.70991570 )
            r = 5
            d_r = 12.5
            len = 34
        elif rv == 28:
            luo_rad = (-428.00000000, 512.00000000, -59.70000000 )
            r = 8
            d_r = 18
            len = 156
        elif rv == 29:
            luo_rad = ( -15.09890165, -640.26377459, 142.65431662  )
            r = 6
            d_r = 12
            len = 60
        elif rv == 30:
            luo_rad = ( 455.99775616, -705.00777231, 321.38351909 )
            r = 4
            d_r = 12
            len = 625

        elif rv == 31:
            luo_rad = (-499.93484604, 517.14755762, -104.46571084)
            r = 5
            d_r = 11
        elif rv == 32:
            luo_rad = (-763.86725194, 378.50264480, 96.99999998)
            r = 4
            d_r = 10
        elif rv == 33:
            luo_rad = ( -23.84879311, -494.30586595, 480.14758457 )
            r = 6
            d_r = 9.5
            len = 38
        elif rv == 34:
            luo_rad = ( 39.34800000, -800.00000000, -119.90000000 )
            r = 8
            d_r = 15
            len = 85
        elif rv == 35:
            luo_rad = ( -76.61909011, -678.15875122, -86.78030803 )
            r = 7
            d_r = 15
            len = 150
        elif rv == 36:
            luo_rad = (2787.58864995, -719.89579363, 52.26333220 ) 
            r = 6.5
            d_r = 14
            len = 115

        elif rv == 37:
            luo_rad = (2692.49611450, -709.97719250, 61.39517525 )
            r = 7
            d_r = 11
            len = 99

        elif rv == 38:
            luo_rad = ( 2777.11290819, -731.81018061, -163.99336632 )
            r = 7
            d_r = 24.5
            len = 91

        elif rv == 39:
            luo_rad = (2723.24266961, -570.57599206, 127.71953981 )
            r = 3
            d_r = 6.8
            len = 20
        
        elif rv == 40:
            luo_rad = ( 2720.70000000, 547.00000000, 629.00000000 )
            r = 4
            d_r = 13
            len = 28
        elif rv == 41:
            luo_rad = (2773.32440459, 718.59601920, -158.52511216 )
            r = 8
            d_r = 18
            len = 116



        info.append(r)
        info.append(d_r)
        info.append(luo_rad)

        circ = gp_Circ(gp_Ax2(gp_Pnt(center[0], center[1], center[2]), occ_utils.as_occ(normal, gp_Dir)), r)
        edge1 = BRepBuilderAPI_MakeEdge(circ, 0., math.pi).Edge()
        edge2 = BRepBuilderAPI_MakeEdge(circ, math.pi, 2*math.pi).Edge()
        outer_wire = BRepBuilderAPI_MakeWire(edge1,edge2).Wire()

        face_maker = BRepBuilderAPI_MakeFace(outer_wire)


        #计算中心轴方向
        surf = BRepAdaptor_Surface(face_maker.Face(), True)
        gp_cyl = surf.Plane()
        axis = gp_cyl.Axis().Direction() # the cylinder axis
        info.append((int(axis.X()), int(axis.Y()), int(axis.Z())))
        shape1 = rv
        info.append(rv)


        
        return face_maker.Face() ,shape1,info
    
