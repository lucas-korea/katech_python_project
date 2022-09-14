import numpy as np
import ouster_header
import os
from tkinter import filedialog
from tkinter import messagebox
import struct
import time

Range_bytes = []
# ref_bytes = []
signal_photon_bytes = []
Range_list = []
ref_list = []
signal_photon_list = []

PACKETS_COUNT = 64
BLOCKS = 16
CHANNEL = 128
BYTES = 24896
TICKS = 88
START_PACKET = 700

Azimuth = np.zeros((BLOCKS * PACKETS_COUNT, CHANNEL))
Azimuth_sum = np.zeros((BLOCKS * PACKETS_COUNT, CHANNEL))
Azimuth_sum_low = np.zeros((BLOCKS * PACKETS_COUNT, CHANNEL))
distance = np.zeros((BLOCKS * PACKETS_COUNT, CHANNEL))  # 128 = channel, 16 * 128 = block * packets
reflectivity = np.zeros((BLOCKS * PACKETS_COUNT, CHANNEL))
signal_photon = np.zeros((BLOCKS * PACKETS_COUNT, CHANNEL))
timestamp = np.zeros((BLOCKS * PACKETS_COUNT, CHANNEL))

# x = np.zeros(BLOCKS * PACKETS_COUNT * CHANNEL)
# y = np.zeros(BLOCKS * PACKETS_COUNT * CHANNEL)
# z = np.zeros(BLOCKS * PACKETS_COUNT * CHANNEL)

angle = np.zeros(128)
Azimuth_intrinsic = np.zeros(128)
angle_low = np.zeros(128)
Azimuth_intrinsic_low = np.zeros(128)
beam_len = ouster_header.beam_intrinsics["lidar_origin_to_beam_origin_mm"] * 0.001
beam_len_low = ouster_header.beam_intrinsics2["lidar_origin_to_beam_origin_mm"] * 0.001
HIGH = 0
LOW = 0
for header_i in range(128):
    angle[header_i] = ouster_header.beam_intrinsics["beam_altitude_angles"][header_i] * np.pi / 180
    Azimuth_intrinsic[header_i] = ouster_header.beam_intrinsics["beam_azimuth_angles"][header_i] * np.pi / 180
    angle_low[header_i] = ouster_header.beam_intrinsics2["beam_altitude_angles"][header_i] * np.pi / 180
    Azimuth_intrinsic_low[header_i] = ouster_header.beam_intrinsics2["beam_azimuth_angles"][header_i] * np.pi / 180


#data encoder 값이 0도 부터 시작하는지 확인 (NIA4차 에서는 pcd 접합부를 차량 후방으로 설정)
def find_start(data):
    index = 0
    index = index + 8  # timestamp
    encoder = data[index + 4: index + 8]
    encoder = (encoder[3] * 256 ** 3 + encoder[2] * 256 ** 2 + encoder[1] * 256 + encoder[0]) / TICKS / 1024 * 360
    if encoder == 0:
        return True
    else:
        return False


#data encoder 값이 180도 부터 시작하는지 확인
def find_180deg(data):
    index = 0
    index = index + 8  # timestamp
    encoder = data[index + 4: index + 8]
    encoder = (encoder[3] * 256 ** 3 + encoder[2] * 256 ** 2 + encoder[1] * 256 + encoder[0]) / TICKS / 1024 * 360
    if encoder == 180:
        return True
    else:
        return False


#xyz position을 계산하고 pcd file에 넣을 array로 합치기, +x 방향 차량 전진, +y는 좌측
def cal_lidar_pos():
    global reflectivity
    x_ = (distance - beam_len) * np.cos(angle) * np.cos(Azimuth_sum) + beam_len * np.cos(Azimuth)
    y_ = (distance - beam_len) * np.cos(angle) * np.sin(Azimuth_sum) + beam_len * np.sin(Azimuth)
    z_ = (distance - beam_len) * np.sin(angle)
    x_ = np.cos(-2 / 180 * np.pi) * x_ - np.sin(-2 / 180 * np.pi) * y_ # 라이다 지그 yaw 기울어짐 2도 수정
    y_ = np.sin(-2 / 180 * np.pi) * x_ + np.cos(-2 / 180 * np.pi) * y_
    return np.stack([-x_, y_, z_, reflectivity], axis=-1).reshape(-1, 4)

#bin style로 생성
def make_bin_PCDfile(point_cloud, lidar_list_dir_path, ymd, hms, frame_num, tick_ct):
    with open(lidar_list_dir_path + "\\" + ymd + "_" + hms + "_" + '{0:06d}'.format(int(frame_num)) + "_" + '{0:06d}'.format(int(tick_ct)) + "_H_upper.pcd", 'w') as f:  # 생성될 pcd file 이름
        f.write(ouster_header.HEADER.format(len(point_cloud), len(point_cloud))) # 미리 지정한 header를 pcd file 위에 write
    with open(lidar_list_dir_path + "\\" + ymd + "_" + hms + "_" + '{0:06d}'.format(int(frame_num)) + "_" + '{0:06d}'.format(int(tick_ct)) + "_H_upper.pcd", 'ab') as f:
        # point_cloud = np.round(point_cloud, 4)
        for i in range(len(point_cloud)):
            f.write(struct.pack("ffff", point_cloud[i][0], point_cloud[i][1], point_cloud[i][2], point_cloud[i][3]))

#ascii style로 생성
def make_ascii_PCDfile(point_cloud, lidar_list_dir_path, ymd, hms, frame_num, tick_ct):
    with open(lidar_list_dir_path + "\\" + ymd + "_" + hms + "_" + '{0:06d}'.format(int(frame_num)) + "_" + '{0:010d}'.format(int(tick_ct)) + ".pcd", 'w') as f:  # 생성될 pcd file 이름
        f.write(ouster_header.HEADER_ascii.format(len(point_cloud), len(point_cloud))) # 미리 지정한 header를 pcd file 위에 write
    with open(lidar_list_dir_path + "\\" + ymd + "_" + hms + "_" + '{0:06d}'.format(int(frame_num)) + "_" + '{0:010d}'.format(int(tick_ct)) + ".pcd", 'a') as f:
        for i in range(len(point_cloud)):
            # for j in range(3):
            #     point_cloud[i][j] = round(point_cloud[i][j], 4)
            f.write(str(point_cloud[i][0]) + ' ' + str(point_cloud[i][1]) + ' ' + str(point_cloud[i][2])
                    + ' ' + str(point_cloud[i][3]) + '\n')


# xyz가 전부 0이거나 Intensity = 0인 경우를 삭제
def rm_zero_point(point_cloud):
    mask_array1 = point_cloud[:, 0] == 0
    mask_array2 = point_cloud[:, 1] == 0
    mask_array3 = point_cloud[:, 2] == 0
    mask_array4 = point_cloud[:, 3] == 0
    mask_all = np.logical_and(mask_array1, mask_array2)
    mask_all = np.logical_and(mask_all, mask_array3)
    mask_all = np.logical_or(mask_all, mask_array4)
    point_cloud = point_cloud[~mask_all]
    return point_cloud


def select_lidar_list():
    files = filedialog.askopenfilenames(initialdir=os.getcwd(),
                                        title="파일을 선택 해 주세요",
                                        filetypes=(("*.txt", "*txt"), ("*.xls", "*xls"), ("*.csv", "*csv")))
    if files == '':
        messagebox.showwarning("경고", "파일을 추가 하세요")  # 파일 선택 안했을 때 메세지 출력
        exit(1)
    lidar_list_dir_path = ("\\".join(list(files)[0].split("/")[0: -1]))  # lidar 데이터 목록 위치 추출
    return files, lidar_list_dir_path


#lidar packet data 중 초반 쓸모없는 데이터 없애기
def crop_start_trash(f):
    while 1:
        try:
            f.read(2)  # 처음에 붙은 0x00 0x00은 없애는 작업
            f.read(50)  # katech header
            if find_start(list(f.read(24896))):
                f.read(2)  # last enter
                break
            f.read(2)  # last enter
        except Exception as e:
            print("error : ", e)
            print("file didn't started. finish")
            break


def main():
    strech_data=[]
    files, lidar_list_dir_path = select_lidar_list()
    print(lidar_list_dir_path, files)
    with open(list(files)[0], 'r') as lidar_f:
        lidar_file_list = lidar_f.readlines()
    time1 = time.time()
    file_num = 0
    for file_name in lidar_file_list:
        packets = []
        file_name = file_name.replace("\n", "")
        print("now converting : ", file_name)
        packets_size = os.path.getsize(file_name) / 24948 / 64
        pcd_num = 0
        frame_number = -1
        frame_i = 0
        tick_ct = -1
        ymd = file_name.replace(".", "_").split("_")[-3]
        hms = file_name.replace(".", "_").split("_")[-2]
        with open(file_name, 'rb') as f:  # 취득데이터 이름
            f.read(880784900)
            crop_start_trash(f)
            while 1:
                try:
                    print(file_num+1,'/', len(lidar_file_list),'\t',pcd_num,"/",packets_size,"frame\t", format((packets_size - pcd_num)*(time.time() - time1)/60, '.2f'),"min left",
                          "   now converting : ", file_name)
                    time1 = time.time()
                    pcd_num = pcd_num + 1
                    for i in range(64):
                        f.read(2) # 처음에 붙은 0x00 0x00은 없애는 작업
                        header = f.read(50)  # katech header
                        data = list(f.read(24896))
                        if find_180deg(data):
                            header = header.decode().replace(" ", "").split("\t")
                            frame_number = header[1]
                            tick_ct = header[2]
                        packets = packets + data
                        f.read(2)  # last enter

                    if (int(tick_ct) > 3901300 and int(tick_ct) < 3901500):
                        print(tick_ct)
                        strech_data.append(packets)
                        parsing_packet(packets)
                        point_cloud = cal_lidar_pos()  # global로 선언된 distance, reflectivity, signal_photon, Azimuth를 조합하여 point cloud data 생성
                        make_bin_PCDfile(point_cloud, lidar_list_dir_path, ymd, hms, frame_i, tick_ct)  # point cloud data를 pcd file로 변환
                    if (int(tick_ct) > 3901500):
                        strech_data  = np.asarray(strech_data)
                        np.save(lidar_list_dir_path + '\\npdata.npy', strech_data)
                        exit(1)
                    frame_i = frame_i + 1
                    packets = []
                except Exception as e:
                    print("error : ", e)
                    print("file finish")
                    break
        file_num = file_num + 1


def crop_zig_shade(i, j):
    if (349 / 180 * np.pi) <= Azimuth_sum[i][j] or Azimuth_sum[i][j] <= (11 / 180 * np.pi):
        distance[i][j] = 0
        reflectivity[i][j] = 0


# ouster lidar packet을 manual에 맞게 parsing
def parsing_packet(data):
    index = 0
    for i in range(PACKETS_COUNT * BLOCKS):
        index = index + 8  # timestamp
        Encoder = data[index + 4: index + 8]
        Encoder = (Encoder[3] * 256 ** 3 + Encoder[2] * 256 ** 2 + Encoder[1] * 256 + Encoder[0])
        Azimuth[i][:] = Encoder / TICKS / 1024 * 2 * np.pi
        Azimuth_sum[i][:] = Azimuth[i][:] + Azimuth_intrinsic
        Azimuth_sum_low[i][:] = Azimuth[i][:] + Azimuth_intrinsic_low
        index = index + 8
        for j in range(CHANNEL):
            Range_bytes = data[index: index + 4]
            ref_bytes = data[index + 4 : index + 5]
            # unused = data[index + 4 : index + 6]
            # signal_photon_bytes = data[index + 6: index + 8]
            distance[i][j] = (Range_bytes[2] * 256 ** 2 + Range_bytes[1] * 256 + Range_bytes[0]) / 1000
            reflectivity[i][j] = ref_bytes[0]
            crop_zig_shade(i, j)
            # signal_photon[i][j] = (signal_photon_bytes[1] * 256 + signal_photon_bytes[0]) #/ 65535
            index = index + 12
        block_stat = data[index: index + 4]
        index = index + 4
        if block_stat != [0xff, 0xff, 0xff, 0xff]:
            print("block status error!!")
            exit(1)


if __name__ == '__main__':
    main()
