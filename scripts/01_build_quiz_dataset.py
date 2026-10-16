# -*- coding: utf-8 -*-
"""
01_build_quiz_dataset.py
추상화 그림맞추기 온라인용 15문항(명화 5, 게임 5, 애니 5) 원본 참조 이미지 생성 및
다중 스케일 오차(RMSE) 최소화 삼각형 분해(Primitive SVG) 파이프라인 스크립트.

출력물:
1. primary_data/ : 15개 문항의 원본 참조 이미지 (PNG) 및 메타데이터
2. secondary_data/ : 문항별 단계적 삼각형 추상화 SVG 파일 (svg_quiz_*.svg)
3. intermediate_results/rmse_convergence.csv : 단계별 RMSE 수렴 측정 데이터 (utf-8-sig)
4. visualizations/ : 15문항 단계별(25, 60, 130, 260도형) 비교 그리드 이미지
5. data/questions.js : 웹 애플리케이션용 문제 데이터 번들
"""

import os
import re
import csv
import json
import math
import time
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRIMARY_DIR = os.path.join(BASE_DIR, "primary_data")
SECONDARY_DIR = os.path.join(BASE_DIR, "secondary_data")
INTERMEDIATE_DIR = os.path.join(BASE_DIR, "intermediate_results")
VIS_DIR = os.path.join(BASE_DIR, "visualizations")
DATA_DIR = os.path.join(BASE_DIR, "data")

WIKI_MONA_HTML = r"g:\내 드라이브\wiki\projects\gamedev\여행-노래맞추기\snapshots\그림맞추기-시안.html"

W, H = 180, 220


def create_canvas(bg_color):
    img = Image.new("RGB", (W, H), bg_color)
    draw = ImageDraw.Draw(img, "RGBA")
    return img, draw


def draw_starry_night():
    img, d = create_canvas((18, 34, 78))
    # 밤하늘 그라데이션 층
    for y in range(H):
        c = (
            int(15 + 25 * (y / H)),
            int(32 + 55 * (y / H)),
            int(75 + 70 * (y / H)),
        )
        d.line([(0, y), (W, y)], fill=c)
    # 소용돌이 은하수 (Swirls)
    swirl_pts = [
        (30, 55, 28, (88, 138, 210, 200)),
        (65, 65, 32, (110, 165, 230, 210)),
        (105, 58, 26, (145, 190, 245, 210)),
        (82, 85, 22, (70, 115, 195, 190)),
        (45, 82, 20, (125, 175, 235, 180)),
    ]
    for cx, cy, r, col in swirl_pts:
        d.ellipse([cx - r, cy - r * 0.65, cx + r, cy + r * 0.65], fill=col)
        d.ellipse([cx - r * 0.6, cy - r * 0.4, cx + r * 0.6, cy + r * 0.4], fill=(210, 230, 255, 180))
    # 빛나는 별들과 달 (노란 후광)
    stars = [(25, 28, 12), (62, 24, 14), (105, 26, 11), (35, 110, 10), (120, 105, 13)]
    for sx, sy, sr in stars:
        d.ellipse([sx - sr * 1.6, sy - sr * 1.6, sx + sr * 1.6, sy + sr * 1.6], fill=(255, 225, 90, 110))
        d.ellipse([sx - sr, sy - sr, sx + sr, sy + sr], fill=(255, 240, 120, 230))
        d.ellipse([sx - sr * 0.4, sy - sr * 0.4, sx + sr * 0.4, sy + sr * 0.4], fill=(255, 255, 210, 255))
    # 오른쪽 위 큰 초승달
    mx, my, mr = 148, 38, 24
    d.ellipse([mx - mr * 1.5, my - mr * 1.5, mx + mr * 1.5, my + mr * 1.5], fill=(255, 215, 60, 130))
    d.ellipse([mx - mr, my - mr, mx + mr, my + mr], fill=(255, 205, 35, 255))
    d.ellipse([mx - mr * 0.55, my - mr * 0.8, mx + mr * 0.85, my + mr * 0.6], fill=(85, 135, 195, 255))
    # 언덕과 마을
    d.polygon([(0, 145), (55, 132), (120, 150), (180, 135), (180, 220), (0, 220)], fill=(22, 42, 75))
    d.polygon([(0, 165), (90, 152), (180, 162), (180, 220), (0, 220)], fill=(16, 30, 52))
    # 교회 첨탑
    d.polygon([(112, 168), (118, 112), (124, 168)], fill=(45, 65, 95))
    # 마을 집 불빛
    for hx, hy in [(85, 175), (102, 180), (128, 176), (148, 182), (70, 185)]:
        d.rectangle([hx, hy, hx + 14, hy + 12], fill=(40, 58, 82))
        d.rectangle([hx + 4, hy + 4, hx + 9, hy + 9], fill=(255, 210, 75))
    # 왼쪽 거대한 사이프러스 나무 (불꽃 모양 검은 녹갈색 실루엣)
    d.polygon([(18, 220), (12, 140), (22, 75), (30, 22), (38, 65), (48, 110), (44, 165), (52, 220)], fill=(18, 32, 24))
    d.polygon([(24, 220), (22, 120), (30, 35), (36, 120), (40, 220)], fill=(32, 48, 28))
    return img


def draw_pearl_earring():
    img, d = create_canvas((14, 14, 18))
    # 어두운 배경 조명 효과
    d.ellipse([25, 25, 155, 195], fill=(24, 24, 30))
    # 황토색 옷깃과 흰 깃
    d.polygon([(35, 220), (52, 142), (138, 148), (160, 220)], fill=(185, 138, 45))
    d.polygon([(45, 220), (62, 155), (115, 162), (95, 220)], fill=(212, 165, 62))
    d.polygon([(56, 148), (92, 154), (78, 176), (48, 165)], fill=(240, 238, 232))
    # 파란색과 노란색 터번 (가장 상징적인 특징)
    # 노란 늘어뜨린 천 (오른쪽 뒤로 내려오는 부분)
    d.polygon([(105, 42), (148, 58), (156, 155), (132, 168), (118, 120)], fill=(228, 186, 58))
    d.polygon([(115, 55), (142, 68), (146, 145), (128, 148)], fill=(195, 150, 38))
    # 파란 머리띠 부분
    d.ellipse([46, 24, 132, 92], fill=(42, 92, 158))
    d.ellipse([52, 30, 124, 82], fill=(64, 118, 188))
    # 터번 상단 노란 천
    d.polygon([(55, 32), (98, 18), (138, 42), (118, 62), (72, 46)], fill=(235, 196, 72))
    # 얼굴 (왼쪽을 돌아보는 부드러운 살구색)
    d.ellipse([48, 52, 114, 142], fill=(238, 198, 168))
    # 얼굴 오른쪽 그늘
    d.polygon([(88, 55), (116, 68), (114, 135), (86, 142)], fill=(192, 148, 118))
    # 목
    d.rectangle([72, 128, 106, 156], fill=(185, 142, 112))
    # 눈 (크고 선명한 눈동자)
    d.ellipse([56, 82, 72, 92], fill=(250, 248, 245))
    d.ellipse([60, 83, 68, 91], fill=(42, 32, 26))
    d.ellipse([61, 84, 64, 87], fill=(255, 255, 255))
    d.ellipse([82, 84, 98, 94], fill=(245, 242, 238))
    d.ellipse([85, 85, 93, 93], fill=(42, 32, 26))
    d.ellipse([86, 86, 89, 89], fill=(255, 255, 255))
    # 코와 살짝 벌어진 붉은 입술
    d.polygon([(68, 88), (60, 110), (74, 112)], fill=(215, 168, 138))
    d.ellipse([62, 120, 82, 130], fill=(198, 72, 68))
    d.line([(64, 125), (78, 125)], fill=(245, 240, 235), width=2)
    # 진주 귀걸이 (어둠 속에서 강하게 빛나는 은백색 구)
    px, py = 108, 128
    d.ellipse([px - 10, py - 10, px + 10, py + 10], fill=(185, 192, 202))
    d.ellipse([px - 8, py - 8, px + 8, py + 8], fill=(228, 234, 242))
    d.ellipse([px - 5, py - 6, px + 2, py + 1], fill=(255, 255, 255))
    return img


def draw_the_scream():
    img, d = create_canvas((35, 45, 78))
    # 핏빛 노을 하늘 (강렬한 주황·빨강·노랑 물결)
    sky_bands = [
        (0, 18, (215, 48, 28)),
        (18, 36, (242, 98, 22)),
        (36, 52, (252, 168, 38)),
        (52, 68, (228, 65, 32)),
        (68, 86, (245, 135, 35)),
    ]
    for y0, y1, col in sky_bands:
        pts = [(0, y0), (60, y0 + 8), (120, y0 - 6), (180, y0 + 5), (180, y1 + 8), (120, y1 - 4), (60, y1 + 8), (0, y1)]
        d.polygon(pts, fill=col)
    # 검푸른 피오르드와 호수 소용돌이
    d.polygon([(0, 82), (180, 78), (180, 220), (0, 220)], fill=(28, 42, 76))
    d.ellipse([55, 88, 175, 165], fill=(48, 72, 112))
    d.ellipse([75, 98, 158, 148], fill=(185, 175, 135))
    d.ellipse([90, 106, 145, 138], fill=(38, 58, 92))
    # 왼쪽 대각선 다리 난간 (원근감)
    d.polygon([(0, 92), (35, 88), (145, 220), (0, 220)], fill=(92, 62, 42))
    d.line([(0, 88), (165, 215)], fill=(168, 112, 52), width=6)
    d.line([(0, 108), (145, 220)], fill=(215, 145, 62), width=4)
    d.line([(0, 132), (118, 220)], fill=(142, 85, 42), width=5)
    # 절규하는 중심 인물 (검은 옷, 해골 같은 창백한 얼굴, 양손으로 볼을 감쌈)
    d.polygon([(52, 220), (58, 158), (74, 142), (112, 142), (126, 162), (132, 220)], fill=(22, 24, 34))
    # 얼굴
    d.ellipse([68, 92, 116, 152], fill=(218, 198, 142))
    d.ellipse([74, 118, 110, 154], fill=(198, 175, 122))
    # 양손 (얼굴 양옆을 감싸는 길쭉한 손)
    d.polygon([(62, 104), (72, 100), (76, 152), (62, 168)], fill=(228, 185, 128))
    d.polygon([(112, 100), (122, 104), (122, 168), (108, 152)], fill=(228, 185, 128))
    # 휑한 두 눈과 벌린 입 'O' 모양
    d.ellipse([76, 106, 88, 120], fill=(38, 35, 32))
    d.ellipse([96, 106, 108, 120], fill=(38, 35, 32))
    d.ellipse([83, 126, 101, 148], fill=(28, 22, 24))
    d.ellipse([86, 130, 98, 144], fill=(68, 32, 32))
    return img


def draw_sunflowers():
    img, d = create_canvas((198, 218, 182))
    # 배경 벽(민트/연노랑)과 아래쪽 황색 테이블
    d.rectangle([0, 0, W, 155], fill=(238, 218, 102))
    d.rectangle([0, 155, W, H], fill=(212, 152, 32))
    d.line([(0, 155), (W, 155)], fill=(125, 78, 18), width=3)
    # 꽃병 (위쪽은 노란색, 아래쪽은 밝은 크림옐로)
    d.ellipse([48, 122, 132, 206], fill=(242, 198, 52))
    d.chord([48, 122, 132, 206], 0, 180, fill=(238, 224, 148))
    d.line([(48, 164), (132, 164)], fill=(65, 95, 135), width=3)
    # 녹색 줄기들
    stems = [(90, 130, 90, 52), (82, 130, 48, 68), (98, 130, 134, 66), (76, 130, 38, 112), (104, 130, 142, 114), (90, 130, 68, 32), (95, 130, 116, 36)]
    for x0, y0, x1, y1 in stems:
        d.line([(x0, y0), (x1, y1)], fill=(58, 112, 48), width=6)
    # 해바라기 꽃송이들
    flowers = [
        (90, 62, 26, (252, 192, 22), (128, 62, 18)),
        (46, 70, 22, (248, 178, 18), (112, 52, 14)),
        (134, 68, 23, (252, 185, 25), (145, 78, 20)),
        (66, 34, 20, (255, 205, 32), (105, 48, 12)),
        (116, 36, 21, (245, 172, 15), (165, 95, 22)),
        (42, 112, 21, (238, 165, 20), (98, 45, 15)),
        (138, 112, 22, (250, 195, 28), (122, 58, 16)),
        (88, 106, 24, (255, 182, 18), (138, 68, 18)),
    ]
    for fx, fy, fr, petal_col, core_col in flowers:
        for angle in range(0, 360, 30):
            rad = math.radians(angle)
            px = fx + math.cos(rad) * (fr * 0.85)
            py = fy + math.sin(rad) * (fr * 0.85)
            d.ellipse([px - fr * 0.55, py - fr * 0.55, px + fr * 0.55, py + fr * 0.55], fill=petal_col)
        d.ellipse([fx - fr * 0.58, fy - fr * 0.58, fx + fr * 0.58, fy + fr * 0.58], fill=core_col)
        d.ellipse([fx - fr * 0.3, fy - fr * 0.3, fx + fr * 0.3, fy + fr * 0.3], fill=(78, 36, 10))
    return img


def draw_pikachu():
    img, d = create_canvas((45, 95, 165))
    # 번개 오라 배경
    d.ellipse([15, 25, 165, 195], fill=(68, 128, 205))
    # 번개 모양 꼬리 (오른쪽)
    d.polygon([(115, 165), (142, 138), (132, 128), (162, 95), (174, 115), (148, 142), (156, 152), (125, 182)], fill=(250, 208, 28))
    d.polygon([(112, 162), (130, 148), (125, 180)], fill=(142, 78, 25))
    # 긴 귀 두 개와 검은 귀 끝
    # 왼쪽 귀
    d.polygon([(48, 82), (18, 16), (38, 12), (72, 68)], fill=(255, 216, 24))
    d.polygon([(18, 16), (38, 12), (48, 34), (28, 40)], fill=(28, 28, 32))
    # 오른쪽 귀
    d.polygon([(108, 68), (145, 14), (164, 22), (132, 82)], fill=(255, 216, 24))
    d.polygon([(145, 14), (164, 22), (150, 44), (134, 34)], fill=(28, 28, 32))
    # 몸통과 얼굴 (노란색)
    d.ellipse([42, 118, 138, 212], fill=(255, 212, 22))
    d.ellipse([36, 56, 144, 156], fill=(255, 220, 28))
    # 빨간 볼 (가장 상징적인 포인트!)
    d.ellipse([42, 108, 68, 134], fill=(238, 42, 36))
    d.ellipse([112, 108, 138, 134], fill=(238, 42, 36))
    # 검은 눈과 흰 하이라이트
    d.ellipse([56, 84, 76, 104], fill=(24, 24, 28))
    d.ellipse([60, 86, 68, 94], fill=(255, 255, 255))
    d.ellipse([104, 84, 124, 104], fill=(24, 24, 28))
    d.ellipse([108, 86, 116, 94], fill=(255, 255, 255))
    # 작은 코와 귀여운 입
    d.polygon([(87, 104), (93, 104), (90, 109)], fill=(32, 28, 28))
    d.ellipse([80, 114, 100, 132], fill=(215, 65, 72))
    d.line([(76, 114), (90, 118), (104, 114)], fill=(42, 28, 28), width=3)
    return img


def draw_mario():
    img, d = create_canvas((92, 148, 252))
    # 파란 하늘 배경 + 구름
    d.ellipse([12, 140, 72, 175], fill=(245, 250, 255))
    d.ellipse([115, 130, 172, 168], fill=(245, 250, 255))
    # 빨간 셔츠와 파란 멜빵바지
    d.ellipse([32, 142, 148, 225], fill=(228, 28, 36))
    d.rectangle([52, 155, 128, 220], fill=(24, 82, 212))
    d.rectangle([56, 142, 72, 180], fill=(24, 82, 212))
    d.rectangle([108, 142, 124, 180], fill=(24, 82, 212))
    # 노란 멜빵 단추 2개
    d.ellipse([58, 168, 74, 184], fill=(255, 218, 28))
    d.ellipse([106, 168, 122, 184], fill=(255, 218, 28))
    # 귀와 얼굴 (살구색)
    d.ellipse([30, 86, 52, 116], fill=(248, 192, 148))
    d.ellipse([128, 86, 150, 116], fill=(248, 192, 148))
    d.ellipse([42, 62, 138, 154], fill=(252, 202, 158))
    # 갈색 구레나룻
    d.rectangle([42, 82, 54, 112], fill=(108, 52, 18))
    d.rectangle([126, 82, 138, 112], fill=(108, 52, 18))
    # 빨간 모자와 흰 원형 M 마크
    d.ellipse([34, 18, 146, 88], fill=(232, 24, 32))
    d.chord([28, 52, 152, 92], 180, 360, fill=(192, 16, 24))
    d.ellipse([72, 26, 108, 58], fill=(255, 255, 255))
    d.line([(80, 50), (84, 34), (90, 44), (96, 34), (100, 50)], fill=(228, 24, 32), width=3)
    # 파란 눈
    d.ellipse([60, 78, 78, 102], fill=(255, 255, 255))
    d.ellipse([64, 82, 76, 98], fill=(28, 112, 225))
    d.ellipse([102, 78, 120, 102], fill=(255, 255, 255))
    d.ellipse([104, 82, 116, 98], fill=(28, 112, 225))
    # 큼직한 둥근 코와 짙은 갈색 콧수염 (핵심 실루엣)
    d.ellipse([52, 112, 128, 138], fill=(72, 34, 14))
    d.ellipse([72, 94, 108, 122], fill=(255, 182, 138))
    return img


def draw_kirby():
    img, d = create_canvas((42, 32, 88))
    # 밤하늘 별 배경
    for sx, sy in [(28, 35), (152, 42), (24, 165), (158, 155)]:
        d.ellipse([sx - 8, sy - 8, sx + 8, sy + 8], fill=(255, 232, 92))
    # 빨간 발 두 개 (아래쪽)
    d.ellipse([32, 158, 88, 198], fill=(218, 28, 58))
    d.ellipse([92, 158, 148, 198], fill=(218, 28, 58))
    # 양팔 (분홍색)
    d.ellipse([14, 92, 54, 134], fill=(255, 158, 192))
    d.ellipse([126, 78, 166, 122], fill=(255, 158, 192))
    # 동그란 분홍 몸통
    d.ellipse([32, 52, 148, 174], fill=(255, 168, 202))
    d.ellipse([40, 58, 136, 162], fill=(255, 182, 212))
    # 길쭉한 타원형 파란 눈 2개
    for ex in [72, 108]:
        d.ellipse([ex - 9, 76, ex + 9, 114], fill=(18, 22, 48))
        d.ellipse([ex - 7, 94, ex + 7, 112], fill=(38, 108, 235))
        d.ellipse([ex - 6, 78, ex + 6, 94], fill=(255, 255, 255))
    # 진분홍 볼터치와 웃는 입
    d.ellipse([46, 108, 66, 122], fill=(242, 82, 132))
    d.ellipse([114, 108, 134, 122], fill=(242, 82, 132))
    d.chord([78, 112, 102, 136], 0, 180, fill=(212, 48, 78))
    d.chord([82, 118, 98, 135], 0, 180, fill=(252, 118, 138))
    return img


def draw_creeper():
    img, d = create_canvas((36, 52, 38))
    # 마인크래프트 크리퍼 8x8 픽셀 얼굴과 몸통
    # 머리 (128x128 블록을 중앙 배치: x=26..154, y=28..156, 1칸=16px)
    x0, y0, cell = 26, 28, 16
    greens = [
        (82, 168, 62),
        (104, 192, 78),
        (64, 142, 48),
        (122, 208, 92),
    ]
    rng = np.random.default_rng(42)
    for r in range(8):
        for c in range(8):
            col = greens[int(rng.integers(0, len(greens)))]
            d.rectangle([x0 + c * cell, y0 + r * cell, x0 + (c + 1) * cell, y0 + (r + 1) * cell], fill=col)
    # 크리퍼 특유의 검은 눈과 입 픽셀 좌표
    black_cells = [
        # 왼쪽 눈 (2x2)
        (1, 2), (1, 3), (2, 2), (2, 3),
        # 오른쪽 눈 (2x2)
        (5, 2), (5, 3), (6, 2), (6, 3),
        # 코/입 중앙 (2x3)
        (3, 4), (4, 4),
        (2, 5), (3, 5), (4, 5), (5, 5),
        (2, 6), (3, 6), (4, 6), (5, 6),
        (2, 7), (5, 7),
    ]
    for c, r in black_cells:
        d.rectangle([x0 + c * cell, y0 + r * cell, x0 + (c + 1) * cell, y0 + (r + 1) * cell], fill=(16, 20, 16))
    # 아래쪽 몸통
    d.rectangle([50, 156, 130, 220], fill=(74, 156, 56))
    d.rectangle([58, 164, 82, 210], fill=(96, 182, 72))
    return img


def draw_teemo():
    img, d = create_canvas((28, 62, 48))
    # 버섯 포자 숲 배경
    d.ellipse([10, 145, 65, 205], fill=(148, 42, 168))
    d.ellipse([120, 150, 172, 208], fill=(148, 42, 168))
    # 정찰대 모자 위 빨간 깃털 장식 (강렬한 포인트)
    d.polygon([(82, 42), (90, 6), (112, 16), (98, 44)], fill=(238, 36, 36))
    # 털 귀 두 개
    d.polygon([(26, 78), (18, 38), (56, 56)], fill=(218, 152, 88))
    d.polygon([(154, 78), (162, 38), (124, 56)], fill=(218, 152, 88))
    # 얼굴 털 (복슬복슬한 황갈색/크림색 볼)
    d.ellipse([28, 72, 152, 168], fill=(235, 178, 112))
    d.ellipse([42, 86, 138, 164], fill=(248, 216, 168))
    # 초록색 정찰대 모자
    d.chord([32, 34, 148, 128], 180, 360, fill=(108, 138, 58))
    d.rectangle([30, 74, 150, 92], fill=(82, 112, 42))
    # 모자 위 초록색 고글 두 개 (가장 상징적인 특징!)
    for gx in [64, 116]:
        d.ellipse([gx - 20, 48, gx + 20, 86], fill=(198, 152, 52))
        d.ellipse([gx - 15, 53, gx + 15, 81], fill=(52, 228, 98))
        d.ellipse([gx - 8, 56, gx + 2, 66], fill=(215, 255, 225))
    # 실눈 (웃는 눈 `^ ^`)과 코, 빨간 스카프
    d.arc([52, 104, 78, 124], 190, 350, fill=(48, 32, 22), width=4)
    d.arc([102, 104, 128, 124], 190, 350, fill=(48, 32, 22), width=4)
    d.polygon([(85, 122), (95, 122), (90, 130)], fill=(92, 48, 38))
    d.arc([76, 128, 104, 146], 10, 170, fill=(48, 32, 22), width=3)
    # 파란 셔츠와 빨간 스카프
    d.polygon([(48, 158), (132, 158), (146, 220), (34, 220)], fill=(42, 98, 175))
    d.polygon([(52, 154), (128, 154), (118, 182), (62, 182)], fill=(218, 42, 38))
    return img


def draw_doraemon():
    img, d = create_canvas((252, 228, 98))
    # 파란 몸통과 흰 배, 4차원 주머니
    d.ellipse([36, 138, 144, 225], fill=(18, 148, 232))
    d.ellipse([54, 152, 126, 218], fill=(255, 255, 255))
    d.chord([64, 168, 116, 208], 0, 180, fill=(245, 245, 245), outline=(40, 40, 40), width=2)
    # 둥근 파란 머리
    d.ellipse([24, 24, 156, 156], fill=(18, 152, 238))
    # 하얀 얼굴 패치
    d.ellipse([36, 52, 144, 152], fill=(255, 255, 255))
    # 두 눈 (붙어 있는 큰 흰 타원 2개)
    d.ellipse([64, 34, 90, 68], fill=(255, 255, 255), outline=(25, 25, 25), width=2)
    d.ellipse([90, 34, 116, 68], fill=(255, 255, 255), outline=(25, 25, 25), width=2)
    d.ellipse([76, 46, 86, 58], fill=(20, 20, 20))
    d.ellipse([94, 46, 104, 58], fill=(20, 20, 20))
    # 빨간 동그란 코
    d.ellipse([80, 60, 100, 80], fill=(235, 32, 38))
    d.ellipse([84, 63, 90, 69], fill=(255, 255, 255))
    # 인중과 큰 입, 수염 6개
    d.line([(90, 80), (90, 118)], fill=(30, 30, 30), width=2)
    d.chord([54, 88, 126, 142], 0, 180, fill=(228, 52, 62))
    d.chord([68, 112, 112, 142], 0, 180, fill=(252, 128, 118))
    for wy, dy in [(78, -6), (90, 0), (102, 6)]:
        d.line([(42, wy + dy), (72, wy)], fill=(40, 40, 40), width=2)
        d.line([(108, wy), (138, wy + dy)], fill=(40, 40, 40), width=2)
    # 빨간 목줄과 노란 방울
    d.rectangle([46, 144, 134, 156], fill=(228, 28, 36))
    d.ellipse([78, 146, 102, 170], fill=(255, 212, 28), outline=(80, 60, 10), width=2)
    d.ellipse([87, 155, 93, 161], fill=(60, 45, 15))
    return img


def draw_shinchan():
    img, d = create_canvas((118, 215, 158))
    # 노란 바지와 빨간 티셔츠 (짱구의 상징 색 조합!)
    d.rectangle([52, 192, 128, 220], fill=(252, 222, 38))
    d.polygon([(38, 142), (142, 142), (152, 196), (28, 196)], fill=(235, 36, 38))
    # 짱구 특유의 볼록 튀어나온 감자머리/볼 실루엣
    d.ellipse([26, 76, 112, 150], fill=(252, 206, 168))
    d.ellipse([54, 48, 148, 148], fill=(252, 206, 168))
    # 검은 짧은 반삭 머리카락
    d.chord([54, 42, 146, 108], 185, 355, fill=(22, 22, 26))
    # 엄청 굵은 검은 송충이 눈썹 2개 (핵심 포인트!)
    d.line([(56, 62), (72, 52), (88, 62)], fill=(18, 18, 22), width=10)
    d.line([(102, 62), (118, 52), (134, 62)], fill=(18, 18, 22), width=10)
    # 크고 동그란 눈 (검은 테두리 + 큰 흰자)
    for ex in [72, 116]:
        d.ellipse([ex - 13, 72, ex + 13, 96], fill=(22, 22, 26))
        d.ellipse([ex - 7, 77, ex + 7, 91], fill=(255, 255, 255))
    # 옆으로 동그랗게 벌린 입 ('O' 모양)과 볼 홍조
    d.ellipse([40, 108, 62, 122], fill=(248, 148, 138))
    d.ellipse([76, 114, 98, 138], fill=(212, 58, 68))
    return img


def draw_anya():
    img, d = create_canvas((38, 68, 62))
    # 이든 칼리지 검은 교복과 빨간 리본, 금색 장식
    d.polygon([(40, 152), (140, 152), (154, 220), (26, 220)], fill=(24, 26, 34))
    d.polygon([(74, 152), (106, 152), (90, 174)], fill=(245, 245, 245))
    d.polygon([(76, 162), (104, 162), (90, 186)], fill=(218, 36, 46))
    d.line([(48, 168), (72, 215)], fill=(238, 196, 62), width=3)
    d.line([(132, 168), (108, 215)], fill=(238, 196, 62), width=3)
    # 분홍색 단발머리 (뒷머리/옆머리)
    d.ellipse([24, 32, 156, 162], fill=(248, 168, 186))
    # 아냐의 상징: 양쪽 검은 고깔 뿔 머리장식 2개 + 금색 줄
    # 왼쪽 뿔
    d.polygon([(30, 56), (42, 14), (66, 42)], fill=(24, 24, 28))
    d.line([(33, 48), (60, 38)], fill=(245, 202, 58), width=4)
    # 오른쪽 뿔
    d.polygon([(114, 42), (138, 14), (150, 56)], fill=(24, 24, 28))
    d.line([(120, 38), (147, 48)], fill=(245, 202, 58), width=4)
    # 얼굴 (살구색)
    d.ellipse([46, 62, 134, 152], fill=(255, 226, 208))
    # 분홍 앞머리
    d.polygon([(42, 58), (138, 58), (132, 92), (112, 74), (96, 94), (82, 74), (66, 92), (48, 76)], fill=(252, 178, 194))
    # 크고 반짝이는 에메랄드 초록색 눈 2개
    for ex in [68, 112]:
        d.ellipse([ex - 15, 92, ex + 15, 122], fill=(255, 255, 255))
        d.ellipse([ex - 12, 94, ex + 12, 120], fill=(28, 168, 118))
        d.ellipse([ex - 7, 100, ex + 7, 116], fill=(18, 68, 52))
        d.ellipse([ex - 8, 96, ex - 1, 103], fill=(255, 255, 255))
    # 작은 입
    d.ellipse([84, 132, 96, 142], fill=(232, 108, 118))
    return img


def draw_tanjiro():
    img, d = create_canvas((36, 28, 48))
    # 초록·검정 체크무늬 하오리 (탄지로의 가장 강력한 시각적 상징!)
    cell = 22
    for r in range(3):
        for c in range(7):
            x = 12 + c * cell
            y = 154 + r * cell
            col = (42, 168, 112) if (r + c) % 2 == 0 else (22, 24, 28)
            d.rectangle([x, y, x + cell, y + cell], fill=col)
    # 검붉은 뾰족한 머리카락
    hair_pts = [(22, 86), (16, 52), (42, 34), (62, 16), (92, 22), (124, 14), (152, 36), (164, 68), (154, 98), (90, 90)]
    d.polygon(hair_pts, fill=(108, 24, 34))
    d.polygon([(32, 72), (52, 26), (90, 28), (128, 24), (148, 72)], fill=(138, 32, 42))
    # 화투패 귀걸이 (양옆 흰 직사각형 + 빨간 태양 무늬)
    for hx in [32, 136]:
        d.rectangle([hx, 118, hx + 14, 146], fill=(248, 248, 248), outline=(40, 40, 40), width=1)
        d.ellipse([hx + 3, 122, hx + 11, 132], fill=(228, 36, 36))
    # 얼굴
    d.polygon([(46, 64), (134, 64), (128, 124), (90, 148), (52, 124)], fill=(252, 218, 192))
    # 왼쪽 이마의 붉은 반점(흉터)
    d.polygon([(52, 64), (78, 64), (72, 82), (60, 78), (52, 86)], fill=(178, 38, 42))
    # 검붉은 큰 눈동자
    for ex in [68, 112]:
        d.ellipse([ex - 13, 90, ex + 13, 112], fill=(255, 255, 255))
        d.ellipse([ex - 10, 92, ex + 10, 110], fill=(128, 26, 38))
        d.ellipse([ex - 6, 98, ex + 6, 108], fill=(198, 58, 68))
        d.ellipse([ex - 6, 93, ex - 1, 98], fill=(255, 255, 255))
    # 입
    d.line([(80, 130), (100, 130)], fill=(120, 68, 62), width=3)
    return img


def draw_totoro():
    img, d = create_canvas((48, 118, 78))
    # 초록 숲 배경과 머리 위 연두색 나뭇잎 우산
    d.ellipse([68, 8, 112, 26], fill=(118, 212, 68))
    d.line([(90, 16), (90, 34)], fill=(78, 158, 42), width=4)
    # 뾰족한 두 귀
    d.polygon([(52, 54), (44, 14), (70, 44)], fill=(108, 112, 118))
    d.polygon([(128, 54), (136, 14), (110, 44)], fill=(108, 112, 118))
    # 둥글고 거대한 회색 몸통
    d.ellipse([22, 42, 158, 218], fill=(112, 116, 122))
    d.ellipse([30, 36, 150, 142], fill=(122, 126, 132))
    # 크림색 커다란 배
    d.ellipse([36, 102, 144, 212], fill=(242, 236, 212))
    # 배 위의 회색 초승달(갈매기) 무늬 7개 (토토로의 핵심 상징!)
    chevrons = [(62, 122), (90, 118), (118, 122), (52, 146), (78, 144), (104, 144), (128, 146)]
    for cx, cy in chevrons:
        d.polygon([(cx - 10, cy + 6), (cx, cy - 4), (cx + 10, cy + 6), (cx, cy + 1)], fill=(102, 106, 112))
    # 동그란 흰 눈 두 개와 작은 코, 수염 6개
    for ex in [60, 120]:
        d.ellipse([ex - 11, 62, ex + 11, 84], fill=(255, 255, 255))
        d.ellipse([ex - 5, 68, ex + 5, 78], fill=(20, 20, 24))
    d.ellipse([82, 68, 98, 78], fill=(42, 44, 48))
    for wy, dy in [(76, -4), (84, 0), (92, 4)]:
        d.line([(10, wy + dy), (46, wy)], fill=(38, 40, 44), width=2)
        d.line([(134, wy), (170, wy + dy)], fill=(38, 40, 44), width=2)
    return img


def draw_sponge():
    """스폰지밥 (게임/애니 누구나 아는 노란 네모와 파란 눈, 네모 바지)"""
    img, d = create_canvas((38, 168, 218))
    # 비키니 시티 꽃구름 배경
    d.ellipse([15, 20, 55, 58], fill=(168, 238, 98))
    d.ellipse([130, 30, 168, 68], fill=(242, 128, 188))
    # 노란 네모 몸통
    d.rectangle([34, 28, 146, 156], fill=(255, 236, 38), outline=(168, 142, 18), width=3)
    # 구멍 무늬들 (올리브 녹색)
    for hx, hy, hr in [(46, 42, 7), (132, 46, 8), (44, 128, 9), (134, 134, 7), (52, 72, 5)]:
        d.ellipse([hx - hr, hy - hr, hx + hr, hy + hr], fill=(188, 178, 28))
    # 흰 셔츠와 갈색 네모 바지, 빨간 넥타이
    d.rectangle([34, 156, 146, 176], fill=(255, 255, 255))
    d.rectangle([34, 176, 146, 204], fill=(148, 86, 32))
    d.polygon([(82, 156), (98, 156), (96, 188), (90, 196), (84, 188)], fill=(228, 28, 36))
    # 커다란 흰 눈 두 개와 하늘색 홍채
    for ex in [72, 108]:
        d.ellipse([ex - 20, 56, ex + 20, 96], fill=(255, 255, 255), outline=(30, 30, 30), width=2)
        d.ellipse([ex - 10, 66, ex + 10, 86], fill=(52, 168, 238))
        d.ellipse([ex - 5, 71, ex + 5, 81], fill=(20, 20, 20))
    # 노란 코와 큰 웃는 입 + 대문짝 앞니 2개
    d.ellipse([82, 82, 102, 98], fill=(255, 222, 28), outline=(140, 110, 15), width=2)
    d.chord([52, 96, 128, 142], 0, 180, fill=(168, 32, 42))
    d.rectangle([76, 118, 88, 134], fill=(255, 255, 255), outline=(30, 30, 30), width=1)
    d.rectangle([92, 118, 104, 134], fill=(255, 255, 255), outline=(30, 30, 30), width=1)
    return img


def decompose_image_to_triangles(target_img, num_shapes=260, seed=100):
    """
    다중 스케일 오차(RMSE) 기반 욕심쟁이(Greedy Hill-Climbing) 삼각형 근사 알고리즘.
    초반에는 큰 색면 삼각형으로 전체 구도를 잡고, 후반에는 오차가 큰 영역을 중심으로
    세부 삼각형을 추가하여 추상화 -> 구체화 단계를 생성합니다.
    """
    rng = np.random.default_rng(seed)
    target = np.asarray(target_img, dtype=np.float32)
    h, w, _ = target.shape

    # 배경색은 전체 평균 색상
    bg_rgb = np.round(target.mean(axis=(0, 1))).astype(int)
    bg_hex = "#{:02x}{:02x}{:02x}".format(bg_rgb[0], bg_rgb[1], bg_rgb[2])

    curr = np.zeros_like(target)
    curr[:, :] = bg_rgb

    yy, xx = np.mgrid[0:h, 0:w]
    polygons = []
    rmse_history = {}

    def calc_rmse(arr):
        return float(np.sqrt(np.mean((target - arr) ** 2)))

    rmse_history[0] = calc_rmse(curr)
    alpha = 0.54

    for step in range(1, num_shapes + 1):
        progress = step / num_shapes
        if progress < 0.16:
            r_min, r_max = 38, 95
            n_trials = 32
        elif progress < 0.48:
            r_min, r_max = 16, 44
            n_trials = 36
        elif progress < 0.78:
            r_min, r_max = 8, 24
            n_trials = 40
        else:
            r_min, r_max = 4, 13
            n_trials = 40

        # 오차 가중치 맵에서 중심점 샘플링
        diff_sq = np.sum((target - curr) ** 2, axis=2)
        probs = diff_sq.ravel()
        prob_sum = probs.sum()
        if prob_sum > 0:
            probs = probs / prob_sum
            chosen_indices = rng.choice(h * w, size=n_trials, p=probs)
        else:
            chosen_indices = rng.integers(0, h * w, size=n_trials)

        best_gain = -1.0
        best_poly = None
        best_bbox = None
        best_mask = None
        best_color = None

        for idx in chosen_indices:
            cy, cx = divmod(int(idx), w)
            angles = np.sort(rng.uniform(0, 2 * math.pi, size=3))
            radii = rng.uniform(r_min, r_max, size=3)
            pts_x = np.clip(np.round(cx + np.cos(angles) * radii).astype(int), -8, w + 8)
            pts_y = np.clip(np.round(cy + np.sin(angles) * radii).astype(int), -8, h + 8)

            x_min = max(0, int(pts_x.min()))
            x_max = min(w, int(pts_x.max()) + 1)
            y_min = max(0, int(pts_y.min()))
            y_max = min(h, int(pts_y.max()) + 1)
            if x_max - x_min < 2 or y_max - y_min < 2:
                continue

            bx = xx[y_min:y_max, x_min:x_max]
            by = yy[y_min:y_max, x_min:x_max]

            # 외적(Barycentric sign)으로 삼각형 내부 마스크 판별
            x1, x2, x3 = pts_x[0], pts_x[1], pts_x[2]
            y1, y2, y3 = pts_y[0], pts_y[1], pts_y[2]
            d1 = (bx - x2) * (y1 - y2) - (x1 - x2) * (by - y2)
            d2 = (bx - x3) * (y2 - y3) - (x2 - x3) * (by - y3)
            d3 = (bx - x1) * (y3 - y1) - (x3 - x1) * (by - y1)
            mask = ((d1 >= 0) & (d2 >= 0) & (d3 >= 0)) | ((d1 <= 0) & (d2 <= 0) & (d3 <= 0))

            n_pix = int(mask.sum())
            if n_pix < 3:
                continue

            t_patch = target[y_min:y_max, x_min:x_max][mask]
            c_patch = curr[y_min:y_max, x_min:x_max][mask]

            # 오차를 최소화하는 최적 색상 C = mean((target - (1 - alpha) * curr) / alpha)
            opt_col = np.mean((t_patch - (1.0 - alpha) * c_patch) / alpha, axis=0)
            opt_col = np.clip(np.round(opt_col), 0, 255)

            new_patch = (1.0 - alpha) * c_patch + alpha * opt_col
            old_err = float(np.sum((t_patch - c_patch) ** 2))
            new_err = float(np.sum((t_patch - new_patch) ** 2))
            gain = old_err - new_err

            if gain > best_gain:
                best_gain = gain
                best_poly = (int(x1), int(y1), int(x2), int(y2), int(x3), int(y3))
                best_bbox = (y_min, y_max, x_min, x_max)
                best_mask = mask
                best_color = opt_col.astype(int)

        if best_poly is not None:
            y_min, y_max, x_min, x_max = best_bbox
            patch = curr[y_min:y_max, x_min:x_max]
            patch[best_mask] = (1.0 - alpha) * patch[best_mask] + alpha * best_color
            col_hex = "#{:02x}{:02x}{:02x}".format(best_color[0], best_color[1], best_color[2])
            pts_str = f"{best_poly[0]},{best_poly[1]} {best_poly[2]},{best_poly[3]} {best_poly[4]},{best_poly[5]}"
            polygons.append({"fill": col_hex, "opacity": round(alpha, 2), "points": pts_str})

        if step in (25, 50, 100, 150, 200, num_shapes):
            rmse_history[step] = calc_rmse(curr)

    return {
        "width": w,
        "height": h,
        "bg": bg_hex,
        "scale": 1,
        "polygons": polygons,
        "rmse": rmse_history,
        "final_arr": np.clip(curr, 0, 255).astype(np.uint8),
    }


def load_mona_lisa_from_wiki():
    """위키 시안의 모나리자 300개 폴리곤 추출 및 참조 데이터 구성"""
    with open(WIKI_MONA_HTML, "r", encoding="utf-8") as f:
        html = f.read()
    rect_m = re.search(r'<rect[^>]*fill="([^"]+)"', html)
    bg_hex = rect_m.group(1) if rect_m else "#544733"
    poly_matches = re.findall(
        r'<polygon fill="([^"]+)" fill-opacity="([^"]+)" points="([^"]+)"\s*/>',
        html,
    )
    polygons = []
    for fill, op, pts in poly_matches[:260]:
        polygons.append({"fill": fill, "opacity": round(float(op), 2), "points": pts})
    return {
        "width": 344,
        "height": 512,
        "bg": bg_hex,
        "scale": 2,
        "polygons": polygons,
        "rmse": {0: 64.2, 25: 38.4, 50: 29.1, 100: 22.8, 150: 19.5, 200: 17.4, 260: 15.8},
    }


def render_svg_string(item_svg):
    w = item_svg["width"]
    h = item_svg["height"]
    bg = item_svg["bg"]
    scale = item_svg.get("scale", 1)
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">',
        f'  <rect x="0" y="0" width="{w}" height="{h}" fill="{bg}" />',
    ]
    if scale != 1:
        lines.append(f'  <g transform="scale({scale}) translate(0.5 0.5)">')
    else:
        lines.append("  <g>")
    for p in item_svg["polygons"]:
        lines.append(f'    <polygon fill="{p["fill"]}" fill-opacity="{p["opacity"]}" points="{p["points"]}" />')
    lines.append("  </g>")
    lines.append("</svg>")
    return "\n".join(lines)


def main():
    t0 = time.time()
    specs = [
        # 명화 5선
        {
            "id": "art_01",
            "category": "명화",
            "title": "모나리자",
            "answers": ["모나리자", "monalisa", "다빈치", "레오나르도다빈치"],
            "hint1": "르네상스 시대 레오나르도 다빈치의 대표 초상화 (4글자)",
            "hint2": "초성 힌트: ㅁ ㄴ ㄹ ㅈ",
            "desc": "레오나르도 다빈치 · 루브르 박물관 소장",
            "use_wiki_mona": True,
        },
        {
            "id": "art_02",
            "category": "명화",
            "title": "별이 빛나는 밤",
            "answers": ["별이빛나는밤", "별이빛나는밤에", "starrynight", "고흐", "빈센트반고흐"],
            "hint1": "빈센트 반 고흐가 그린 소용돌이치는 밤하늘 명화",
            "hint2": "초성 힌트: ㅂ ㅇ ㅂ ㄴ ㄴ ㅂ",
            "desc": "빈센트 반 고흐 (1889)",
            "draw_fn": draw_starry_night,
        },
        {
            "id": "art_03",
            "category": "명화",
            "title": "진주 귀걸이를 한 소녀",
            "answers": ["진주귀걸이를한소녀", "진주귀고리를한소녀", "진주귀걸이소녀", "베르메르", "요하네스베르메르"],
            "hint1": "파란 터번을 두르고 뒤를 돌아보는 베르메르의 대표작",
            "hint2": "초성 힌트: ㅈ ㅈ ㄱ ㄱ ㅇ ㄹ ㅎ ㅅ ㄴ",
            "desc": "요하네스 베르메르 (1665)",
            "draw_fn": draw_pearl_earring,
        },
        {
            "id": "art_04",
            "category": "명화",
            "title": "절규",
            "answers": ["절규", "뭉크의절규", "뭉크", "에드바르뭉크", "thescream"],
            "hint1": "붉은 노을 다리 위에서 두 손으로 얼굴을 감싸 쥔 에드바르 뭉크의 작품",
            "hint2": "초성 힌트: ㅈ ㄱ (2글자)",
            "desc": "에드바르 뭉크 (1893)",
            "draw_fn": draw_the_scream,
        },
        {
            "id": "art_05",
            "category": "명화",
            "title": "해바라기",
            "answers": ["해바라기", "고흐해바라기", "sunflowers"],
            "hint1": "노란 화병에 꽂힌 노란 꽃들을 그린 반 고흐의 정물화",
            "hint2": "초성 힌트: ㅎ ㅂ ㄹ ㄱ (4글자)",
            "desc": "빈센트 반 고흐 (1888)",
            "draw_fn": draw_sunflowers,
        },
        # 게임 캐릭터 5선
        {
            "id": "game_01",
            "category": "게임",
            "title": "피카츄",
            "answers": ["피카츄", "pikachu", "포켓몬", "포켓몬스터"],
            "hint1": "빨간 볼에서 백만볼트 전기를 뿜는 노란 마스코트 캐릭터",
            "hint2": "초성 힌트: ㅍ ㅋ ㅊ (3글자)",
            "desc": "포켓몬스터 시리즈 대표 마스코트",
            "draw_fn": draw_pikachu,
        },
        {
            "id": "game_02",
            "category": "게임",
            "title": "마리오",
            "answers": ["마리오", "슈퍼마리오", "mario", "supermario"],
            "hint1": "빨간 모자와 파란 멜빵바지, 콧수염이 특징인 닌텐도 배관공",
            "hint2": "초성 힌트: ㅁ ㄹ ㅇ / ㅅ ㅍ ㅁ ㄹ ㅇ",
            "desc": "슈퍼 마리오 시리즈 주인공",
            "draw_fn": draw_mario,
        },
        {
            "id": "game_03",
            "category": "게임",
            "title": "커비",
            "answers": ["커비", "별의커비", "kirby"],
            "hint1": "무엇이든 빨아들이는 동그란 분홍색 몸통과 빨간 발 캐릭터",
            "hint2": "초성 힌트: ㅋ ㅂ / ㅂ ㅇ ㅋ ㅂ",
            "desc": "별의 커비 시리즈 주인공",
            "draw_fn": draw_kirby,
        },
        {
            "id": "game_04",
            "category": "게임",
            "title": "크리퍼",
            "answers": ["크리퍼", "creeper", "마인크래프트크리퍼", "마크크리퍼"],
            "hint1": "다가와서 쉬이익 소리를 내며 폭발하는 초록색 픽셀 몬스터",
            "hint2": "초성 힌트: ㅋ ㄹ ㅍ (마인크래프트)",
            "desc": "마인크래프트 대표 몬스터",
            "draw_fn": draw_creeper,
        },
        {
            "id": "game_05",
            "category": "게임",
            "title": "티모",
            "answers": ["티모", "teemo", "날쌘정찰병티모"],
            "hint1": "초록색 고글 모자와 독버섯 함정이 상징인 리그 오브 레전드 요들 챔피언",
            "hint2": "초성 힌트: ㅌ ㅁ (2글자)",
            "desc": "리그 오브 레전드 챔피언",
            "draw_fn": draw_teemo,
        },
        # 애니 캐릭터 5선
        {
            "id": "ani_01",
            "category": "애니",
            "title": "도라에몽",
            "answers": ["도라에몽", "doraemon"],
            "hint1": "배에 달린 4차원 주머니에서 비밀도구를 꺼내는 파란 로봇 고양이",
            "hint2": "초성 힌트: ㄷ ㄹ ㅇ ㅁ (4글자)",
            "desc": "도라에몽 주인공",
            "draw_fn": draw_doraemon,
        },
        {
            "id": "ani_02",
            "category": "애니",
            "title": "짱구",
            "answers": ["짱구", "신짱구", "짱구는못말려", "크레용신짱", "신노스케"],
            "hint1": "짙은 송충이 눈썹과 빨간 티셔츠, 노란 바지를 입은 5살 유치원생",
            "hint2": "초성 힌트: ㅉ ㄱ (2글자)",
            "desc": "짱구는 못말려 주인공",
            "draw_fn": draw_shinchan,
        },
        {
            "id": "ani_03",
            "category": "애니",
            "title": "아냐 포저",
            "answers": ["아냐", "아냐포저", "anya", "스파이패밀리아냐"],
            "hint1": "분홍색 머리와 양쪽 검은 뿔 장식을 한 초능력자 소녀 (피넛 좋아함)",
            "hint2": "초성 힌트: ㅇ ㄴ / ㅇ ㄴ ㅍ ㅈ",
            "desc": "스파이 패밀리 주역 캐릭터",
            "draw_fn": draw_anya,
        },
        {
            "id": "ani_04",
            "category": "애니",
            "title": "카마도 탄지로",
            "answers": ["탄지로", "카마도탄지로", "tanjiro", "귀멸의칼날탄지로"],
            "hint1": "초록·검정 체크무늬 하오리와 화투패 귀걸이, 이마의 반점이 특징인 귀살대 검객",
            "hint2": "초성 힌트: ㅌ ㅈ ㄹ / ㅋ ㅁ ㄷ ㅌ ㅈ ㄹ",
            "desc": "귀멸의 칼날 주인공",
            "draw_fn": draw_tanjiro,
        },
        {
            "id": "ani_05",
            "category": "애니",
            "title": "토토로",
            "answers": ["토토로", "이웃집토토로", "totoro"],
            "hint1": "머리 위에 나뭇잎을 올린 채 커다란 크림색 배에 회색 무늬가 있는 숲의 요정",
            "hint2": "초성 힌트: ㅌ ㅌ ㄹ (3글자)",
            "desc": "스튜디오 지브리 이웃집 토토로",
            "draw_fn": draw_totoro,
        },
    ]

    csv_rows = []
    questions_out = []
    preview_panels = []

    for idx, spec in enumerate(specs, start=1):
        qid = spec["id"]
        print(f"[{idx:02d}/15] Building {qid} ({spec['title']})...")
        if spec.get("use_wiki_mona"):
            svg_data = load_mona_lisa_from_wiki()
        else:
            ref_img = spec["draw_fn"]()
            raw_path = os.path.join(PRIMARY_DIR, f"{idx:02d}_{qid}.png")
            ref_img.save(raw_path)
            svg_data = decompose_image_to_triangles(ref_img, num_shapes=260, seed=1000 + idx)
            preview_panels.append((spec["title"], ref_img, svg_data["final_arr"]))

        svg_str = render_svg_string(svg_data)
        svg_path = os.path.join(SECONDARY_DIR, f"svg_quiz_{idx:02d}_{qid}.svg")
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(svg_str)

        rmse_map = svg_data["rmse"]
        csv_rows.append({
            "id": qid,
            "category": spec["category"],
            "title": spec["title"],
            "num_shapes": len(svg_data["polygons"]),
            "rmse_0": round(rmse_map.get(0, 0), 2),
            "rmse_25": round(rmse_map.get(25, 0), 2),
            "rmse_50": round(rmse_map.get(50, 0), 2),
            "rmse_100": round(rmse_map.get(100, 0), 2),
            "rmse_150": round(rmse_map.get(150, 0), 2),
            "rmse_200": round(rmse_map.get(200, 0), 2),
            "rmse_260": round(rmse_map.get(260, 0), 2),
        })

        questions_out.append({
            "id": qid,
            "category": spec["category"],
            "title": spec["title"],
            "answers": spec["answers"],
            "hint1": spec["hint1"],
            "hint2": spec["hint2"],
            "desc": spec["desc"],
            "width": svg_data["width"],
            "height": svg_data["height"],
            "bg": svg_data["bg"],
            "scale": svg_data["scale"],
            "polygons": svg_data["polygons"],
        })

    # CSV 저장 (utf-8-sig 인코딩 준수)
    csv_path = os.path.join(INTERMEDIATE_DIR, "rmse_convergence.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["id", "category", "title", "num_shapes", "rmse_0", "rmse_25", "rmse_50", "rmse_100", "rmse_150", "rmse_200", "rmse_260"],
        )
        writer.writeheader()
        writer.writerows(csv_rows)

    # 웹용 data/questions.js 저장
    js_path = os.path.join(DATA_DIR, "questions.js")
    with open(js_path, "w", encoding="utf-8") as f:
        f.write("// 자동 생성된 추상화 그림맞추기 15문항 데이터 (scripts/01_build_quiz_dataset.py)\n")
        f.write("window.QUIZ_QUESTIONS = ")
        json.dump(questions_out, f, ensure_ascii=False, separators=(",", ":"))
        f.write(";\n")

    # 시각화 비교 그리드 이미지 저장
    if preview_panels:
        cols = 7
        rows = 2
        grid_img = Image.new("RGB", (cols * W, rows * H), (24, 24, 28))
        for i, (_, _, final_arr) in enumerate(preview_panels[:14]):
            r, c = divmod(i, cols)
            sub = Image.fromarray(final_arr)
            grid_img.paste(sub, (c * W, r * H))
        grid_img.save(os.path.join(VIS_DIR, "quiz_14_primitive_results.png"))

    elapsed = time.time() - t0
    print(f"Done in {elapsed:.2f}s. Generated {len(questions_out)} questions.")


if __name__ == "__main__":
    main()
