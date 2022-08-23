import sys
import numpy as np
import pandas as pd
import math
import cv2
import struct
np.set_printoptions(threshold=sys.maxsize)
RefImage = np.zeros((128, 2048), dtype=np.uint8)

def parsing_binPCD2asciiPCD(PCD, type_list, count_list):
    start = 0
    lines = [[]]
    pack_str = ""
    format_str = ""
    byte_len = 0
    type_list[-1] = type_list[-1].replace('\n', '')
    type_list[-1] = type_list[-1].replace('\r', '')
    for i in range(len(type_list)):
        if (type_list[i] == "F"):
            for j in range(int(count_list[i])):
                pack_str = pack_str + "f"
                format_str = format_str + "{:.6f} "
                byte_len = byte_len + 4
        elif (type_list[i] == "U"):
            for j in range(int(count_list[i])):
                pack_str = pack_str + "B"
                format_str = format_str + "{} "
                byte_len = byte_len + 1
    line_i = 0
    format_str = format_str.split(" ")
    Depth_img = np.zeros((128,1024), dtype=np.uint8)
    intensity_img = np.zeros((128, 1024), dtype=np.uint8)
    HorizonResol = 360 / (1024)
    for col in range(1024):

        for row in range(128):
            scalar_fileds = struct.unpack(pack_str, PCD[start: start + byte_len])  # B:부호없는 정수, c:문자
            Depth_img[row, col] = np.sqrt(scalar_fileds[0]*scalar_fileds[0] + scalar_fileds[1]*scalar_fileds[1] + scalar_fileds[2]*scalar_fileds[2])
            intensity_img[row, col] = scalar_fileds[3]
            start = start + byte_len

            # HorizonIndex = int((math.atan(scalar_fileds[0] / scalar_fileds[1]) / math.pi * 360.0 + 180) / HorizonResol)
            # if scalar_fileds[1] < 0:
            #     HorizonIndex += 1024
            # HorizonIndex += 1024
            # if HorizonIndex >2047:
            #     HorizonIndex -= 2048
            # RefImage[row][HorizonIndex] += scalar_fileds[3]

    return Depth_img, intensity_img

def MakePCDimg(file_name):
    Origin_pcd_f = open(file_name, 'rb')
    header = []
    field_list = []
    size_list = []
    type_list = []
    count_list = []
    breaker = False

    line = Origin_pcd_f.readline().decode()
    line = line.replace("\r", "")
    line = line.replace("\n", "")
    header.append(line + '\n')
    while line:
        line = Origin_pcd_f.readline().decode()
        line = line.replace("\r", "")
        line = line.replace("\n", "")
        words = line.split(' ')
        if words[0] == "DATA":
            if words[1] != "binary":
                breaker = True
                print("skip {} cause it is not bin type".format(file_name))
                break
            header.append("DATA ascii\n")
            break
        elif words[0] == "FIELDS":
            for j in range(len(words) - 1):
                field_list.append(words[j + 1])
        elif words[0] == "SIZE":
            for j in range(len(words) - 1):
                size_list.append(words[j + 1])
        elif words[0] == "TYPE":
            for j in range(len(words) - 1):
                type_list.append(words[j + 1])
        elif words[0] == "COUNT":
            for j in range(len(words) - 1):
                count_list.append(words[j + 1])
        header.append(line + '\n')

    PCD_data_part = Origin_pcd_f.read()  # 헤더까지 다 읽은 기록이 있기 때문에, 나머지를 다 읽으면 PCD 데이터 부분이다.
    Depth_img, intensity_img = parsing_binPCD2asciiPCD(PCD_data_part, type_list, count_list)
    col_depth_img = cv2.applyColorMap(Depth_img, cv2.COLORMAP_JET)
    col_intensity_img = cv2.applyColorMap(intensity_img, cv2.COLORMAP_JET)
    return(Depth_img, intensity_img)