import random
import math
import numpy as np

from OCC.Core.BRepPrimAPI import BRepPrimAPI_MakeBox
from OCC.Core.BRepMesh import BRepMesh_IncrementalMesh
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_MakeWire, BRepBuilderAPI_MakeEdge,BRepBuilderAPI_Transform 
from OCC.Core.gp import gp_Pnt
from OCC.Extend.TopologyUtils import TopologyExplorer
from OCC.Core.TopoDS import TopoDS_Compound
from OCC.Core.BRep import BRep_Builder
from OCC.Core.TopLoc import TopLoc_Location
from OCC.Core.STEPConstruct import stepconstruct_FindEntity
from OCC.Core.TCollection import TCollection_HAsciiString
from OCC.Core.STEPControl import STEPControl_Writer, STEPControl_AsIs,STEPControl_Reader
from OCC.Core.gp import gp_Pnt,gp_Trsf, gp_Vec,gp_Ax2,gp_Dir ,gp_Ax1
from OCC.Core.BRepAlgoAPI import BRepAlgoAPI_Cut
import Utils.shape_factory as shape_factory
import Utils.parameters as param
import Utils.occ_utils as occ_utils

from Features.o_ring import ORing
from Features.through_hole import ThroughHole
from Features.round import Round
from Features.chamfer import Chamfer
from Features.triangular_passage import TriangularPassage
from Features.rectangular_passage import RectangularPassage
from Features.six_sides_passage import SixSidesPassage
from Features.triangular_through_slot import TriangularThroughSlot
from Features.rectangular_through_slot import RectangularThroughSlot
from Features.circular_through_slot import CircularThroughSlot
from Features.rectangular_through_step import RectangularThroughStep
from Features.two_sides_through_step import TwoSidesThroughStep
from Features.slanted_through_step import SlantedThroughStep
from Features.blind_hole import BlindHole
from Features.triangular_pocket import TriangularPocket
from Features.rectangular_pocket import RectangularPocket
from Features.six_sides_pocket import SixSidesPocket
from Features.circular_end_pocket import CircularEndPocket
from Features.rectangular_blind_slot import RectangularBlindSlot
from Features.v_circular_end_blind_slot import VCircularEndBlindSlot
from Features.h_circular_end_blind_slot import HCircularEndBlindSlot
from Features.triangular_blind_step import TriangularBlindStep
from Features.circular_blind_step import CircularBlindStep
from Features.rectangular_blind_step import RectangularBlindStep



feat_names = ['chamfer', 'through_hole', 'triangular_passage', 'rectangular_passage', '6sides_passage',
              'triangular_through_slot', 'rectangular_through_slot', 'circular_through_slot',
              'rectangular_through_step', '2sides_through_step', 'slanted_through_step', 'Oring', 'blind_hole',
              'triangular_pocket', 'rectangular_pocket', '6sides_pocket', 'circular_end_pocket',
              'rectangular_blind_slot', 'v_circular_end_blind_slot', 'h_circular_end_blind_slot',
              'triangular_blind_step', 'circular_blind_step', 'rectangular_blind_step', 'round', 'stock']

feat_classes = {"chamfer": Chamfer, "through_hole": ThroughHole, "triangular_passage": TriangularPassage,
                "rectangular_passage": RectangularPassage, "6sides_passage": SixSidesPassage,
                "triangular_through_slot": TriangularThroughSlot, "rectangular_through_slot": RectangularThroughSlot,
                "circular_through_slot": CircularThroughSlot, "rectangular_through_step": RectangularThroughStep,
                "2sides_through_step": TwoSidesThroughStep, "slanted_through_step": SlantedThroughStep, "Oring": ORing,
                "blind_hole": BlindHole, "triangular_pocket": TriangularPocket, "rectangular_pocket": RectangularPocket,
                "6sides_pocket": SixSidesPocket, "circular_end_pocket": CircularEndPocket,
                "rectangular_blind_slot": RectangularBlindSlot, "v_circular_end_blind_slot": VCircularEndBlindSlot,
                "h_circular_end_blind_slot": HCircularEndBlindSlot, "triangular_blind_step": TriangularBlindStep,
                "circular_blind_step": CircularBlindStep, "rectangular_blind_step": RectangularBlindStep,
                "round": Round}

# feat_names = ['chamfer', 'through_hole', 
#               'rectangular_through_step', '2sides_through_step', 'slanted_through_step', 'blind_hole','stock']

# feat_classes = {"chamfer": Chamfer, "through_hole": ThroughHole,  "rectangular_through_step": RectangularThroughStep,
#                 "2sides_through_step": TwoSidesThroughStep, "slanted_through_step": SlantedThroughStep, 
#                 "blind_hole": BlindHole}

through_blind_features = ["triangular_passage", "rectangular_passage", "6sides_passage", "triangular_pocket",
                          "rectangular_pocket", "6sides_pocket", "through_hole", "blind_hole", "circular_end_pocket",
                          "Oring"]


def write_step_wth_prediction(filename, shape, prediction):
    writer = STEPControl_Writer()
    writer.Transfer(shape, STEPControl_AsIs)

    finderp = writer.WS().TransferWriter().FinderProcess()

    loc = TopLoc_Location()
    topo = TopologyExplorer(shape)
    faces = list(topo.faces())

    counter = 0
    for face in faces:
        item = stepconstruct_FindEntity(finderp, face, loc)
        if item is None:
            print(face)
            continue
        item.SetName(TCollection_HAsciiString(str(prediction[counter])))
        counter += 1

    writer.Write(filename)



def triangulate_shape(shape):
    linear_deflection = 0.1
    angular_deflection = 0.5
    mesh = BRepMesh_IncrementalMesh(shape, linear_deflection, False, angular_deflection, True)
    mesh.Perform()
    assert mesh.IsDone()


def generate_stock_dims(larger_stock):
    if larger_stock: # too much features need larger stock for avoiding wrong topology
        stock_min_x = param.stock_min_x * 2
        stock_min_y = param.stock_min_y * 2
        stock_min_z = param.stock_min_z * 2
    else:
        stock_min_x = param.stock_min_x
        stock_min_y = param.stock_min_y
        stock_min_z = param.stock_min_z
    param.stock_dim_x = random.uniform(stock_min_x, param.stock_max_x)
    param.stock_dim_y = random.uniform(stock_min_y, param.stock_max_y)
    param.stock_dim_z = random.uniform(stock_min_z, param.stock_max_z)

# 生成第二个块体
def generate_stock_2_dims(n,x,y,z):
    if n == [2,1]:
        dim = random.uniform(10, 15)
        pos = gp_Pnt(0, 0, dim)

        dx = x
        dy = y
        dz = 0.000001
    elif n == [2,-1]:
        dim = random.uniform(z-15, z-10)
        pos = gp_Pnt(0, 0, dim)
        dx = x
        dy = y
        dz = 0.000001
        dim = z - dim
    
    elif n == [0,1]:
        dim = random.uniform(10, 15)
        pos = gp_Pnt(dim, 0, 0)
        dx = 0.000001
        dy = y
        dz = z
    elif n == [0,-1]:
        dim = random.uniform(x-15, x-10)
        pos = gp_Pnt(dim, 0, 0)
        dx = 0.000001
        dy = y
        dz = z
        dim = x - dim

    elif n == [1,1]:
        dim = random.uniform(10, 15)
        pos = gp_Pnt(0, dim, 0)
        dy = 0.000001
        dx = x
        dz = z
    elif n == [1,-1]:
        dim = random.uniform(y-15, y-10)
        pos = gp_Pnt(0, dim, 0)
        dy = 0.000001
        dx = x
        dz = z
        dim = y - dim

    #     x1 = random.uniform(-x, x/2-10)
    #     x2 = random.uniform(x/2+10, 2*x)
    #     dim_x = x2-x1
    #     y1 = random.uniform(-y, y/2-10)
    #     y2 = random.uniform(y/2+10, 2*y)
    #     dim_y = y2-y1
    #     pos1 = gp_Pnt(x1, y1, z)
    #     dim_z = random.uniform(z, z+50)

    return  pos, dx, dy, dz,dim

def rearrange_combo(combination):
    transition_feats = []
    step_feats = []
    slot_feats = []
    through_feats = []
    blind_feats = []
    o_ring_feats = []

    for cnt, val in enumerate(combination):
        if val == param.feat_names.index("chamfer") or val == param.feat_names.index("round"):
            transition_feats.append(val)
        elif val == param.feat_names.index("rectangular_through_step") \
                or val == param.feat_names.index("2sides_through_step") \
                or val == param.feat_names.index("slanted_through_step") \
                or val == param.feat_names.index("triangular_blind_step") \
                or val == param.feat_names.index("circular_blind_step") \
                or val == param.feat_names.index("rectangular_blind_step"):
            step_feats.append(val)

        elif val == param.feat_names.index("triangular_through_slot") \
                or val == param.feat_names.index("rectangular_through_slot") \
                or val == param.feat_names.index("circular_through_slot") \
                or val == param.feat_names.index("rectangular_blind_slot") \
                or val == param.feat_names.index("v_circular_end_blind_slot") \
                or val == param.feat_names.index("h_circular_end_blind_slot"):
            slot_feats.append(val)

        elif val == param.feat_names.index("through_hole") \
                or val == param.feat_names.index("triangular_passage") \
                or val == param.feat_names.index("rectangular_passage") \
                or val == param.feat_names.index("6sides_passage"):
            through_feats.append(val)

        elif val == param.feat_names.index("blind_hole") \
                or val == param.feat_names.index("triangular_pocket") \
                or val == param.feat_names.index("rectangular_pocket") \
                or val == param.feat_names.index("6sides_pocket") \
                or val == param.feat_names.index("circular_end_pocket"):
            blind_feats.append(val)

        elif val == param.feat_names.index("Oring"):
            o_ring_feats.append(val)

    new_combination = step_feats + slot_feats + through_feats + blind_feats + o_ring_feats + transition_feats

    return new_combination


def rearrange_combo_planar(combination):
    transition_feats = []
    step_feats = []
    slot_feats = []
    through_feats = []
    blind_feats = []

    for cnt, val in enumerate(combination):
        if val == param.feat_names.index("chamfer"):
            transition_feats.append(val)
        elif val == param.feat_names.index("rectangular_through_step") \
                or val == param.feat_names.index("2sides_through_step") \
                or val == param.feat_names.index("slanted_through_step") \
                or val == param.feat_names.index("triangular_blind_step") \
                or val == param.feat_names.index("rectangular_blind_step"):
            step_feats.append(val)

        elif val == param.feat_names.index("triangular_through_slot") \
                or val == param.feat_names.index("rectangular_through_slot") \
                or val == param.feat_names.index("rectangular_blind_slot"):
            slot_feats.append(val)

        elif val == param.feat_names.index("triangular_passage") \
                or val == param.feat_names.index("rectangular_passage") \
                or val == param.feat_names.index("6sides_passage"):
            through_feats.append(val)
        elif val == param.feat_names.index("triangular_pocket") \
                or val == param.feat_names.index("rectangular_pocket") \
                or val == param.feat_names.index("6sides_pocket"):
            blind_feats.append(val)

    new_combination = step_feats + slot_feats + through_feats + blind_feats + transition_feats

    return new_combination



def shape_from_directive(combo):
    try_cnt = 0
    find_edges = True
    # combo = rearrange_combo(combo) # rearrange machining feature combinations
    combo.sort(reverse=True)
    count = 0
    bounds = []
    N_Choice = random.choice([[0,1],[0,-1],[1,-1],[1,1],[2,1],[2,-1]])
    # if combo.count(1) >= 2:
    Fa_list = {}

    while True:

        # random stock size
        if len(combo) >= 10:
            # too much features need larger stock for avoiding wrong topology
            generate_stock_dims(larger_stock=True)
        else:
            generate_stock_dims(larger_stock=False)
        # create stock
        shape_gen1 = BRepPrimAPI_MakeBox(param.stock_dim_x, param.stock_dim_y, param.stock_dim_z).Shape()

        #生成第二个块
        pos,dx,dy,dz,dim = generate_stock_2_dims(N_Choice, param.stock_dim_x, param.stock_dim_y, param.stock_dim_z)
        shape_gen2 = BRepPrimAPI_MakeBox(pos, dx, dy, dz).Shape()

        cut = BRepAlgoAPI_Cut(shape_gen1, shape_gen2)  
        shape = cut.Shape()  

        # shape = TopoDS_Compound()
        # builder = BRep_Builder()
        # builder.MakeCompound(shape)

        # builder.Add(shape, shape_gen1)
        # builder.Add(shape, shape_gen2)

        # non-feature faces are labeled as stok
        label_map = shape_factory.map_from_name(shape, param.feat_names.index('stock'))

        for fid in combo:
            feat_name = param.feat_names[fid]
            if feat_name == "chamfer":
                edges = occ_utils.list_edge(shape)
                # create new feature object
                new_feat = feat_classes[feat_name](shape, label_map, param.min_len,
                                                   param.clearance, param.feat_names, edges)
                shape, label_map, edges = new_feat.add_feature()

                if len(edges) == 0:
                    break

            elif feat_name == "round":
                if find_edges:
                    edges = occ_utils.list_edge(shape)
                    find_edges = False

                new_feat = feat_classes[feat_name](shape, label_map, param.min_len,
                                                   param.clearance, param.feat_names, edges)
                shape, label_map, edges = new_feat.add_feature()

                if len(edges) == 0:
                    break

            elif feat_name == "through_hole":
                triangulate_shape(shape) # mesh curved surface ???
        
                new_feat = feat_classes[feat_name](shape, label_map, param.min_len, param.clearance, param.feat_names)
        
                if count == 0:
           
                    shape, label_map, bounds,info,sn= new_feat.add_feature(bounds,dim, N_Choice=N_Choice, find_bounds=True)

                    reader = STEPControl_Reader()
                    reader.ReadFile(f'{sn}.stp')
                    reader.TransferRoots()
                    shape1 = reader.OneShape()

                    ax = info[6]
                    if ax[0] != 0 :
                        rad = 90
                        ax_xyz = [0,-ax[0],0]

                    elif ax[1] != 0:
                        rad = 90
                        ax_xyz = [ax[1],0,0]

                    elif ax[2] == 1:
                        rad = 180
                        ax_xyz = [0,1,0]
                    elif ax[2] == -1:
                        rad = 0
                        ax_xyz = [0,0,1]

                    # 螺栓原点坐标
                    ro_id = info[5]
                    axis = gp_Ax1(gp_Pnt(ro_id[0], ro_id[1], ro_id[2] ), gp_Dir(ax_xyz[0], ax_xyz[1], ax_xyz[2]))  
                    trsf_rotation = gp_Trsf()  
                    trsf_rotation.SetRotation(axis,  math.radians(rad))  
                    flipped_builder = BRepBuilderAPI_Transform(shape1, trsf_rotation, True)  
                    if flipped_builder.IsDone():  
                        flipped_builder.Build()
                        flipped_shape = flipped_builder.Shape()  
                    else:  
                        print("Failed to rotate shape")  

                    tx = info[0] - ro_id[0]
                    ty = info[1] - ro_id[1]
                    tz = info[2] - ro_id[2]
                    translation_vector = gp_Vec(tx, ty, tz)  
  
                    # 创建一个平移变换  
                    trsf = gp_Trsf()  
                    trsf.SetTranslation(translation_vector) 
                    transformed_builder = BRepBuilderAPI_Transform(flipped_shape, trsf, True)  
                    if transformed_builder.IsDone():  
                        transformed_shape = transformed_builder.Shape()   
                    else:  
                        print("Failed to transform shape") 


                    if feat_name in through_blind_features:                            
                        count += 1

                else: # I think it should find bounds after each feature created besides from inner bounds
                    # may slow generation speed
                    shape,label_map, bounds,info,sn= new_feat.add_feature(bounds,dim, N_Choice=N_Choice, find_bounds=True) # orignial: False

                    reader = STEPControl_Reader()
                    reader.ReadFile(f'{sn}.stp')
                    reader.TransferRoots()
                    shape1 = reader.OneShape()

                    ax = info[6]
                    if ax[0] != 0 :
                        rad = 90
                        ax_xyz = [0,-ax[0],0]

                    elif ax[1] != 0:
                        rad = 90
                        ax_xyz = [ax[1],0,0]

                    elif ax[2] == 1:
                        rad = 180
                        ax_xyz = [0,1,0]
                    elif ax[2] == -1:
                        rad = 0
                        ax_xyz = [0,0,1]

                    # 螺栓原点坐标
                    ro_id = info[5]
                    axis = gp_Ax1(gp_Pnt(ro_id[0], ro_id[1], ro_id[2] ), gp_Dir(ax_xyz[0], ax_xyz[1], ax_xyz[2]))  
                    trsf_rotation = gp_Trsf()  
##################################################################################################
                    #### 偏置生成调整
                    trsf_rotation.SetRotation(axis,  math.radians(rad))  #random.randint(-15, 15)
                    flipped_builder = BRepBuilderAPI_Transform(shape1, trsf_rotation, True)  
                    if flipped_builder.IsDone():  
                        flipped_builder.Build()
                        flipped_shape = flipped_builder.Shape()  
                    else:  
                        print("Failed to rotate shape")  

                    tx = info[0] - ro_id[0] 
                    ty = info[1] - ro_id[1] 
                    tz = info[2] - ro_id[2] 
                    translation_vector = gp_Vec(tx, ty, tz)  
  
                    # 创建一个平移变换  
                    trsf = gp_Trsf()  
                    trsf.SetTranslation(translation_vector) 
                    transformed_builder = BRepBuilderAPI_Transform(flipped_shape, trsf, True)  
                    if transformed_builder.IsDone():  
                        transformed_shape = transformed_builder.Shape()   
                    else:  
                        print("Failed to transform shape") 

                    count += 1
            
                Fa_list[tuple(info)] = transformed_shape
                

            # elif feat_name == "blind_hole":
            #     triangulate_shape(shape) # mesh curved surface ???
            #     new_feat = feat_classes[feat_name](shape, label_map, param.min_len, param.clearance, param.feat_names)
            #     if count == 0:
               
            #         shape, label_map, bounds,shape1= new_feat.add_feature(bounds, find_bounds=True)
                   
        
            #         if feat_name in through_blind_features:
            #             count += 1

            #     else: # I think it should find bounds after each feature created besides from inner bounds
            #         # may slow generation speed
            #         shape,label_map, bounds,shape1= new_feat.add_feature(bounds, find_bounds=True) # orignial: False
            #         count += 1
                 

            else:
                triangulate_shape(shape) # mesh curved surface ???
                new_feat = feat_classes[feat_name](shape, label_map, param.min_len, param.clearance, param.feat_names)
                if count == 0:
               
                    shape, label_map, bounds= new_feat.add_feature(bounds,dim,N_Choice=None ,find_bounds=True)
              
        
                    if feat_name in through_blind_features:
                        count += 1

                else: # I think it should find bounds after each feature created besides from inner bounds
                    # may slow generation speed
                    shape,label_map, bounds= new_feat.add_feature(bounds, dim, N_Choice=None, find_bounds=True) # orignial: False
                    count += 1
            

        if shape is not None:
            break

        try_cnt += 1
        if try_cnt > len(combo):
            shape = None
            label_map = None
            break

    return shape,label_map,Fa_list


def display_bounds(bounds, display, color):
    for bound in bounds:
        rect = [gp_Pnt(bound[0][0], bound[0][1], bound[0][2]),
                gp_Pnt(bound[1][0], bound[1][1], bound[1][2]),
                gp_Pnt(bound[2][0], bound[2][1], bound[2][2]),
                gp_Pnt(bound[3][0], bound[3][1], bound[3][2]),
                gp_Pnt(bound[0][0], bound[0][1], bound[0][2])]

        wire_sect = BRepBuilderAPI_MakeWire()

        for i in range(len(rect) - 1):
            edge_sect = BRepBuilderAPI_MakeEdge(rect[i], rect[i+1]).Edge()
            wire_sect.Add(edge_sect)

        sect = wire_sect.Wire()

        display.DisplayShape(sect, update=True, color=color)

    return display


def get_segmentaion_label(faces_list, seg_map):
    ''' 
    Create map between face id and segmentaion label
    '''
    faceid_label_map = {}
    for face in faces_list:
        face_idx = faces_list.index(face)    
        faceid_label_map[face_idx] = seg_map[face]

    return faceid_label_map


def get_instance_label(faces_list, num_faces, inst_map):
    '''
    Create relation_matrix describing the feature instances
    '''
    relation_matrix = np.zeros((num_faces, num_faces), dtype=np.uint8)

    for inst in inst_map:
        for row_inst_face in inst:
            if row_inst_face not in faces_list:
                print('WARNING! mssing face', row_inst_face.__hash__()) 
                continue
            row_face_idx = faces_list.index(row_inst_face) 
            # In the face_idx row，all instance faces are labeled as 1
            for col_inst_face in inst:
                if col_inst_face not in faces_list:
                    print('WARNING! mssing face', col_inst_face.__hash__()) 
                    continue
                col_face_idx = faces_list.index(col_inst_face)
                # pythonocc index starts from 1
                relation_matrix[row_face_idx][col_face_idx] = 1

    assert relation_matrix.nonzero(), 'relation_matrix is empty'
    assert np.allclose(relation_matrix, relation_matrix.T), 'relation_matrix is not symmetric'

    return relation_matrix.tolist()


def save_json_data(pathname, data):
    import json
    """Export a data to a json file"""
    with open(pathname, 'w', encoding='utf8') as fp:
        json.dump(data, fp, indent=4, ensure_ascii=False, sort_keys=False)


if __name__ == '__main__':
    combo = [1,1,1]
    # shape, label_map,S1 = shape_from_directive(combo)
    # shape1,f1,f2 = S1

    shape, label_map,Fa_list = shape_from_directive(combo)
    shape1,f1,f2 = Fa_list
    print(Fa_list)

    compound = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(compound)

    builder.Add(compound, shape)
    builder.Add(compound, shape1)



    feature_list1 = list(TopologyExplorer(f1.Shape()).faces())
    feature_list2 = list(TopologyExplorer(f2.Shape()).faces())


    faces_list = list(TopologyExplorer(shape1).faces())
    faces_list_new = list(TopologyExplorer(shape1).faces())
    for i in range(len(faces_list)):
        if faces_list[i] in feature_list1 or faces_list[i] in feature_list2:
            faces_list_new.remove(faces_list[i])
    dic_faces = {key: 0 for key in faces_list}
    for k in dic_faces:
        if k == faces_list_new[0]:
            dic_faces[k] = 1
    # print(dic_faces)
    
    # print(label_map)
    seg_map, inst_label, bottom_map = label_map

    # print(seg_map)
    # print(inst_label)

    count = len(combo)
    i = inst_label[count-1][0]
    seg_map[i] = 5
    seg_map = {k: 0 if v != 5 else v for k, v in seg_map.items()}

    seg_map.update(dic_faces)
    print(seg_map)
    # for f in seg_map.keys():
    #     print(f.__hash__())
    # print('--------------------------------------------------')
    # for f in bottom_map.keys():
    #     print(f.__hash__())

    faces_list = occ_utils.list_face(compound)
    print(faces_list)


    # Create map between face id and segmentaion label
    seg_label = get_segmentaion_label(faces_list, seg_map)
    assert len(seg_label) == len(faces_list)
    print(seg_label)

    values_list = list(seg_label.values())
    write_step_wth_prediction('label1.step',compound,values_list)

 

    # Create relation_matrix describing the feature instances
    # relation_matrix = get_instance_label(faces_list, len(faces_list), inst_label)
    # assert len(seg_label) == len(relation_matrix)
    # for row in relation_matrix:
    #     print(row)

    # Create map between face id and botto identification label
    # bottom_label = get_segmentaion_label(faces_list, bottom_map)
    # assert len(seg_label) == len(bottom_label)
    # print(bottom_label)

    # save step


    writer = STEPControl_Writer()


    writer.Transfer(shape, STEPControl_AsIs)
    # writer.Write('test1.step')

    writer.Transfer(shape1, STEPControl_AsIs)
    writer.Write('test2.step')
   

    

    
    data = [
        ['test2', {'seg': seg_label}]
        # ['test1', {'seg': seg_label , 'inst': relation_matrix, 'bottom': bottom_label}]
    ]
    # save label
    save_json_data('test2.json', data)
