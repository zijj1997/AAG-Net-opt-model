# -*- coding: utf-8 -*-
"""Creates dataset from random combination of machining features

Used to generate dataset of stock cube with machining features applied to them.
The number of machining features is defined by the combination range.
To change the parameters of each machining feature, please see parameters.py
"""

from itertools import combinations_with_replacement
from itertools import repeat
import Utils.shape as shape
import random
import os
import gc
import pickle
import time
from tqdm import tqdm
from multiprocessing.pool import Pool

from OCC.Extend.TopologyUtils import TopologyExplorer
from OCC.Core.STEPControl import STEPControl_Writer, STEPControl_AsIs
from OCC.Core.TopLoc import TopLoc_Location
from OCC.Core.STEPConstruct import stepconstruct_FindEntity
from OCC.Core.TCollection import TCollection_HAsciiString
from OCC.Core.TopoDS import (
    TopoDS_Solid,
    TopoDS_Compound,
    TopoDS_CompSolid,
)
from OCC.Extend.DataExchange import STEPControl_Writer
from OCC.Core.BRep import BRep_Builder
from OCC.Core.TopoDS import TopoDS_Compound

import Utils.occ_utils as occ_utils
import feature_creation
import math


def distance_3d(point1, point2):

    x1, y1, z1, r1 = point1[0:4]
    x2, y2, z2, r2 = point2[0:4]
    DIS = math.sqrt((x2 - x1)**2 + (y2 - y1)**2 + (z2 - z1)**2)
    L = DIS - (r1 + r2 + 6) 
    return L



def shape_with_fid_to_step(filename, SHAPE,faces_list,id_map, save_face_label=True):
    """Save shape to a STEP file format.

    :param filename: Name to save shape as.
    :param shape: Shape to be saved.
    :param id_map: Variable mapping labels to faces in shape.
    :return: None
    """
    writer = STEPControl_Writer()
    # for shape in SHAPE:
        # writer = STEPControl_Writer()
        # writer.Transfer(shape, STEPControl_AsIs)
        # writer.Transfer(shape1, STEPControl_AsIs)
    writer.Transfer(SHAPE, STEPControl_AsIs)

    if save_face_label:
        finderp = writer.WS().TransferWriter().FinderProcess()
        faces = faces_list
        loc = TopLoc_Location()
        for face in faces:
            item = stepconstruct_FindEntity(finderp, face, loc)
            if item is None:
                print(face)
                continue
            item.SetName(TCollection_HAsciiString(str(id_map[face])))

    writer.Write(filename)

def shape_with_fid_to_step2(filename, shape, shape1, shape2, faces_list,id_map, save_face_label=True):
    """Save shape to a STEP file format.

    :param filename: Name to save shape as.
    :param shape: Shape to be saved.
    :param id_map: Variable mapping labels to faces in shape.
    :return: None
    """
    writer = STEPControl_Writer()
    writer.Transfer(shape, STEPControl_AsIs)
    writer.Transfer(shape1, STEPControl_AsIs)
    writer.Transfer(shape2, STEPControl_AsIs)

    if save_face_label:
        finderp = writer.WS().TransferWriter().FinderProcess()
        faces = faces_list
        loc = TopLoc_Location()
        for face in faces:
            item = stepconstruct_FindEntity(finderp, face, loc)
            if item is None:
                print(face)
                continue
            item.SetName(TCollection_HAsciiString(str(id_map[face])))

    writer.Write(filename)

def directive(combo, count):
    shape_name = str(count)
    shapes, labels = feature_creation.shape_from_directive(combo)

    seg_map, inst_map = labels[0], labels[1]
    faces_list = occ_utils.list_face(shape)
    # Create map between face id and segmentaion label
    seg_label = feature_creation.get_segmentaion_label(faces_list, seg_map)
    # Create relation_matrix describing the feature instances
    relation_matrix = feature_creation.get_instance_label(faces_list, len(seg_map), inst_map)

    return shapes, shape_name, (seg_label, relation_matrix)


def save_shape(SHAPE,faces_list, step_path, label_map):
    print(f"Saving: {step_path}")
    shape_with_fid_to_step(step_path, SHAPE,faces_list,label_map)

# def save_shape2(shape,shape1,shape2,faces_list, step_path, label_map):
#     print(f"Saving: {step_path}")
#     shape_with_fid_to_step2(step_path, shape, shape1,shape2,faces_list,label_map)

def save_label(shape_name, pathname, seg_label):
    import json
    """
    Export a data to a json file
    """

    values_list = list(seg_label.values())

    with open(pathname, 'w', encoding='utf8') as fp:
        json.dump(values_list, fp, indent=4, ensure_ascii=False, sort_keys=False)

def save_label1(shape_name, pathname, seg_label):
    import json
    """
    Export a data to a json file
    """

    data = [
        [shape_name, {'seg': seg_label}]
    ]
    with open(pathname, 'w', encoding='utf8') as fp:
        json.dump(data, fp, indent=4, ensure_ascii=False, sort_keys=False)


def generate_shape(args):
    """
    Generate num_shapes random shapes in dataset_dir
    :param arg: List of [shape directory path, shape name, machining feature combo]
    :return: None
    """
    dataset_dir, combo = args
    f_name, combination = combo

    num_try = 0 # first try
    while True:
        num_try += 1
        print('try count', num_try)
        if num_try > 3:
            # fails too much, pass
            print('number of fails > 3, pass')
            break

        try:
            shape, labels,Fa_list = feature_creation.shape_from_directive(combination)
        except Exception as e:
            print('Fail to generate:')
            print(e)
            continue

        if shape is None:
            print('generated shape is None')
            continue

        
        # from topologyCheker import TopologyChecker
        # check shape topology
        # too slow, we perform TopologyChecker after step generated
        # topochecker = TopologyChecker()
        # if not topochecker(shape):
        #     print("generated shape has wrong topology")
        #     continue
    
        # check generated shape has supported type (TopoDS_Solid, TopoDS_Compound, TopoDS_CompSolid)
        if not isinstance(shape, (TopoDS_Solid, TopoDS_Compound, TopoDS_CompSolid)):
            print('generated shape is {}, not supported'.format(type(shape)))
            continue
        
        seg_map, inst_label, bottom_map = labels

        if len(combination) != len(inst_label):
            print('generated shape has wrong number of seg labels {} with step faces {}. '.format(
                len(combination), len(inst_label)))
            continue
        print(Fa_list)
    
        # len_1 = combination.count(1)
        # len_c = len(combination)
        # for i in range(len_c-len_1,len_c):
        #     if len(inst_label[i]) != 1:
        #         kong = None
        #         print('break')
        #         break
        #     else:
        #         kong = 1
            

        # if kong is None:
        #     print('continue')
        #     continue


        


        if len(Fa_list) <= 2:
            lc = combination.count(1)
            keys = list(Fa_list.keys()) 
            shape1 = Fa_list[keys[lc-1]]
         
            compound = TopoDS_Compound()
            builder = BRep_Builder()
            builder.MakeCompound(compound)
            builder.Add(compound, shape)
            builder.Add(compound, shape1)


            faces_list = list(TopologyExplorer(shape1).faces())
            dic_faces = {key: keys[lc-1][7] for key in faces_list}

            faces_list = occ_utils.list_face(compound)
            if len(faces_list) == 0:
                print('empty shape')
                continue
    
            count = len(combination)
            print(count)
            print(inst_label)
            for i in range(len(inst_label[count-1])):
                top_face = inst_label[count-1][i]
                seg_map[top_face] = 25
            # seg_map = {k: 0 if v != 2 else v for k, v in seg_map.items()}
            seg_map.update(dic_faces)
            seg_label = feature_creation.get_segmentaion_label(faces_list, seg_map)
            SHAPE = [shape,shape1]
            COMpound = compound
            
    
        
        elif 5>=len(Fa_list)>2:
            lc = combination.count(1)
            keys = list(Fa_list.keys()) 
            S1 = Fa_list[keys[len(Fa_list)-1]]
            for i in range(len(keys)):
                rr = keys[len(Fa_list)-1][4] + keys[i][4]
                if distance_3d(keys[len(Fa_list)-1],keys[i]) >rr:
                    S2 = Fa_list[keys[i]]
                    lx = i
                    break
                else:
                    S2 = None
                    continue
        
            shape1 = S1

            compound = TopoDS_Compound()
            builder = BRep_Builder()
            builder.MakeCompound(compound)
            builder.Add(compound, shape)
            builder.Add(compound, shape1)
            faces_list1 = list(TopologyExplorer(shape1).faces())
            dic_faces1 = {key: keys[len(Fa_list)-1][7] for key in faces_list1}
            SHAPE = [shape,shape1]

            count = len(combination)
            print(count)
            print(inst_label)
            for i in range(len(inst_label[count-1])):
                top_face = inst_label[count-1][i]
                seg_map[top_face] = 25
        
            if S2 is not None:
                shape2 = S2
                builder.Add(compound, shape2)
                faces_list2 = list(TopologyExplorer(shape2).faces())
                dic_faces2 = {key: keys[lx][7] for key in faces_list2}
                for j in range(len(inst_label[count-lc+lx])):
                    top_face = inst_label[count-lc+lx][j]
                    seg_map[top_face] = 25
                SHAPE.append(shape2)
            


            faces_list = occ_utils.list_face(compound)
            if len(faces_list) == 0:
                print('empty shape')
                continue
    
            # seg_map = {k: 0 if v != 2 else v for k, v in seg_map.items()}
            seg_map.update(dic_faces1)
            if S2 is not None:
                seg_map.update(dic_faces2)
            faces_list = occ_utils.list_face(compound)
            seg_label = feature_creation.get_segmentaion_label(faces_list, seg_map)
            COMpound = compound


        elif len(Fa_list)>5:
            lc = combination.count(1)
            keys = list(Fa_list.keys()) 
            S1 = Fa_list[keys[len(Fa_list)-1]]
            for i in range(len(keys)):
                rr = keys[len(Fa_list)-1][4] + keys[i][4]
                if distance_3d(keys[len(Fa_list)-1],keys[i]) >rr:
                    S2 = Fa_list[keys[i]]
                    le = i
                    for j in range(len(keys)):
                        rrr = keys[j][4] + keys[i][4]
                        if distance_3d(keys[len(Fa_list)-1],keys[j]) >rr and distance_3d(keys[i],keys[j]) >rrr:
                            S3 = Fa_list[keys[j]]
                            lg = j
                            break
                        else:
                            S3 = None
                            continue
                    break
                else:
                    S2 = None
                    continue
           
            shape1 = S1

            compound = TopoDS_Compound()
            builder = BRep_Builder()
            builder.MakeCompound(compound)
            builder.Add(compound, shape)
            builder.Add(compound, shape1)
            faces_list1 = list(TopologyExplorer(shape1).faces())
            dic_faces1 = {key: keys[len(Fa_list)-1][7] for key in faces_list1}
            SHAPE = [shape,shape1]

            count = len(combination)
            print(count)
            print(inst_label)
            for i in range(len(inst_label[count-1])):
                top_face = inst_label[count-1][i]
                seg_map[top_face] = 25
        
            if S2 is not None:
                shape2 = S2
                builder.Add(compound, shape2)
                faces_list2 = list(TopologyExplorer(shape2).faces())
                dic_faces2 = {key: keys[le][7] for key in faces_list2}
                for j in range(len(inst_label[count-lc+le])):
                    top_face = inst_label[count-lc+le][j]
                    seg_map[top_face] = 25
                SHAPE.append(shape2)
                if S3 is not None:
                    shape3 = S3
                    builder.Add(compound, shape3)
                    faces_list3 = list(TopologyExplorer(shape3).faces())
                    dic_faces3 = {key: keys[lg][7] for key in faces_list3}
                    for k in range(len(inst_label[count-lc+lg])):
                        top_face = inst_label[count-lc+lg][k]
                        seg_map[top_face] = 25
                    SHAPE.append(shape3)

            faces_list = occ_utils.list_face(compound)
            if len(faces_list) == 0:
                print('empty shape')
                continue
    
            # seg_map = {k: 0 if v != 2 else v for k, v in seg_map.items()}
            seg_map.update(dic_faces1)
            if S2 is not None:
                seg_map.update(dic_faces2)
                if S3 is not None:
                    seg_map.update(dic_faces3)
            faces_list = occ_utils.list_face(compound)
            seg_label = feature_creation.get_segmentaion_label(faces_list, seg_map)
            COMpound = compound
        


   
        # shape1,f1,f2 = S1
        # compound = TopoDS_Compound()
        # builder = BRep_Builder()
        # builder.MakeCompound(compound)
        # builder.Add(compound, shape)
        # builder.Add(compound, shape1)

        # feature_list1 = list(TopologyExplorer(f1.Shape()).faces())
        # feature_list2 = list(TopologyExplorer(f2.Shape()).faces())
        # faces_list = list(TopologyExplorer(shape1).faces())
        # faces_list_new = list(TopologyExplorer(shape1).faces())
        # for i in range(len(faces_list)):
        #     if faces_list[i] in feature_list1 or faces_list[i] in feature_list2:
        #         faces_list_new.remove(faces_list[i])
        # dic_faces = {key: 0 for key in faces_list}
        # for k in dic_faces:
        #     if k == faces_list_new[0]:
        #         dic_faces[k] = 1

        # get the corresponding semantic segmentaion, instance and bottom labels
       
        # faces_list = occ_utils.list_face(compound)
        # if len(faces_list) == 0:
        #     print('empty shape')
        #     continue
  
        # count = len(combination)
        # print(count)
        # print(inst_label)
        # i = inst_label[count-1][0]
        # seg_map[i] = 2
        # # seg_map = {k: 0 if v != 2 else v for k, v in seg_map.items()}
        # seg_map.update(dic_faces)
        # faces_list = occ_utils.list_face(compound)

        # Create map between face id and segmentaion label
        # seg_label = feature_creation.get_segmentaion_label(faces_list, seg_map)
        if len(seg_label) != len(faces_list):
            print('generated shape has wrong number of seg labels {} with step faces {}. '.format(
                len(seg_label), len(faces_list)))
            continue


        # Create relation_matrix describing the feature instances
        # relation_matrix = feature_creation.get_instance_label(faces_list, len(seg_map), inst_label)
        # if len(relation_matrix) != len(faces_list):
        #     print('generated shape has wrong number of instance labels {} with step faces {}. '.format(
        #         len(relation_matrix), len(faces_list)))
        #     continue
        # # Create map between face id and botto identification label
        # bottom_label = feature_creation.get_segmentaion_label(faces_list, bottom_map)
        # if len(bottom_label) != len(faces_list):
        #     print('generated shape haswrong number of bottom labels {} with step faces {}. '.format(
        #         len(bottom_label), len(faces_list)))
        #     continue



        # save step and its labels
        shape_name = str(f_name)
        step_path = os.path.join(dataset_dir, 'steps')
        label_path = os.path.join(dataset_dir, 'labels')
        label_path1 = os.path.join(dataset_dir, 'label1s')
        step_path = os.path.join(step_path, shape_name + '.step')
        label_path = os.path.join(label_path, shape_name + '.json')
        label_path1 = os.path.join(label_path1, shape_name + '.json')
        try:
            # if len(Fa_list) <= 2:
            #     save_shape(shape,shape1,faces_list, step_path, seg_map)
            # if 5>=len(Fa_list)>2:
            #     save_shape2(shape,shape1,shape2,faces_list, step_path, seg_map)
            save_shape(COMpound,faces_list, step_path, seg_map)
            save_label(shape_name, label_path, seg_label)
            save_label1(shape_name, label_path1, seg_label)
        except Exception as e:
            print('Fail to save:')
            print(e)
            continue
        print('SUCCESS')
        break # success
    return


def initializer():
    import signal
    """
    Ignore CTRL+C in the worker process.
    """
    signal.signal(signal.SIGINT, signal.SIG_IGN)



if __name__ == '__main__':
    # Parameters to be set before use
    dataset_scale = 'tiny' # or large
    num_features = 3 # for large dataset, use full classes
    # for tiny dataset, only common features
    # Through hole, Blind hole, Rectangular pocket, Rectangular through slot, Round, Chamfer
    tiny_dataset_cand_feats = [1, 8 ,12, 17, 22]
    cand_feat_weights = [0.2, 0.2,0.3,0.3,0.2]
    dataset_dir = 'data4/5'
    combo_range = [3, 5]
    num_samples = 600
    num_workers = 12

    if not os.path.exists(dataset_dir):
        os.mkdir(dataset_dir)
    step_path = os.path.join(dataset_dir, 'steps')
    label_path = os.path.join(dataset_dir, 'labels')
    label_path1 = os.path.join(dataset_dir, 'label1s')
    if not os.path.exists(step_path):
        os.mkdir(step_path)
    if not os.path.exists(label_path):
        os.mkdir(label_path)
    if not os.path.exists(label_path1):
        os.mkdir(label_path1)

    # old feature combination generation
    # combos = []
    # for num_combo in range(combo_range[0], combo_range[1]):
    #     combos += list(combinations_with_replacement(range(num_features), num_combo))

    # print('total combinations: ', len(combos))
    # random.shuffle(combos)
    # test_combos = combos[:num_samples]
    # del combos

    combos = []
    for idx in range(num_samples):
        num_inter_feat = random.randint(combo_range[0], combo_range[1])
        if dataset_scale == 'large':
            combo = [random.randint(0, num_features-1) for _ in range(num_inter_feat)] # no stock face
        elif dataset_scale == 'tiny':
            combo = random.choices(tiny_dataset_cand_feats, weights=cand_feat_weights, k=num_inter_feat)
            combo.append(1)

        now =  time.localtime()
        now_time = time.strftime("%Y%m%d_%H%M%S", now)
        file_name = now_time + '_' + str(idx)
        combos.append((file_name, combo))

    if num_workers == 1:
        for combo in combos:
            generate_shape((dataset_dir, combo))
    elif num_workers > 1: # multiprocessing
        pool = Pool(processes=num_workers, initializer=initializer)
        try:
            result = list(tqdm(pool.imap(generate_shape, zip(repeat(dataset_dir), combos)), 
                            total=len(combos)))
        except KeyboardInterrupt:
            pool.terminate()
            pool.join()
    else:
        AssertionError('error number of workers')
    
    gc.collect()


