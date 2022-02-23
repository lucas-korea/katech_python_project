import os
import struct

PATH = "D:\\NIA4차 대비 실도로 주행 sample PNGPCD 3case"
PCDlist = [file for file in os.listdir(PATH) if os.path.splitext(file)[1] == '.pcd']
print(PCDlist)

for j in range(len(PCDlist)):
    print(j/len(PCDlist))
    with open(PATH + '\\' + PCDlist[j], 'rb') as f:
        header = b''
        for i in range(11):
            header += f.readline()
        point_cloud = f.read()

    with open(PATH + '\\' + PCDlist[j].split('.')[0] + '_convert.pcd', 'ab') as f:
        f.write(header)
        for i in range(int(len(point_cloud)/16)):
            onepoint = struct.unpack('ffff', point_cloud[0 + i * 16:16 + i * 16])
            f.write(struct.pack('ffff', -onepoint[1], onepoint[0], onepoint[2], onepoint[3]))
