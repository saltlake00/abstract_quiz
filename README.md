# 추상화 그림맞추기 온라인 (Abstract Art Quiz Online)

도형(삼각형)이 하나씩 쌓이며 점진적으로 드러나는 추상화 그림을 모든 참가자가 동시에 보면서 실시간 채팅으로 정답을 맞히는 온라인 멀티플레이 웹 게임입니다.

* **라이브 배포 주소**: `https://saltlake00.github.io/abstract_quiz/`
* **저장소 주소**: `https://github.com/saltlake00/abstract_quiz`

## 1. 주요 구현 기능 (현재 배포 완료)
* **모두가 같은 화면 공유**: 방에 입장한 모든 플레이어가 실시간으로 그려지는 260개 도형 추상화 캔버스, 타이머 및 단계별 힌트, 실시간 채팅창, 점수판을 한 화면에서 함께 봅니다.
* **방 생성, 비밀번호 잠금 및 클립보드 복사**:
  * 누구나 방을 생성할 수 있으며, 선택적으로 비밀번호(FNV1a 64비트 결합 해시 검증)를 설정하여 허가된 참가자만 입장하도록 제한할 수 있습니다.
  * 홈 화면 및 방 내부 상단에서 **방 코드 복사**와 **초대 링크 복사**를 지원합니다.
* **다중 수식어 랜덤 닉네임 생성**:
  * 접속 및 새로고침마다 `[상황 수식어 25종] + [행동 수식어 30종] + [화가·야채·동물 명사 62종]` 조합(약 4만 8천여 가지)으로 개성 있는 기본 닉네임이 자동 입력되며, `🎲 랜덤` 버튼으로 즉시 다시 뽑을 수 있습니다.
* **무료 온라인 실시간 연동 (4중 하이브리드 및 중복 패킷 제거)**:
  1. **MQTT over WSS (`wss://broker.emqx.io:8084/mqtt`)**: 방화벽 및 모바일 LTE 대칭형 NAT(CGNAT) 환경에서도 100% 연결을 보장하는 실시간 웹소켓 브로커 채널
  2. **WebRTC (PeerJS 무료 클라우드)**: 브라우저 간 P2P 데이터 채널 연결
  3. **BroadcastChannel**: 동일 PC 내 여러 브라우저 탭 간 지연 시간 0ms 즉시 동기화
  4. **Firebase Realtime Database (선택)**: 상단 `연동 설정`에서 데이터베이스 URL 입력 시 중앙 DB 모드로 확장 지원
* **한국어 입력(IME) 보호 및 스포일러 방지 채점**:
  * 한글 조합 중(`isComposing`) 엔터 입력 시 글자 잘림 및 중복 전송을 방지합니다.
  * 공백·특수문자 제거 정규화 및 5글자 이상 정답의 편집거리 1 오타 허용(`levenshtein <= 1`)을 지원하며, 정답 메시지는 자동으로 가려지고 점수로 환산됩니다.
* **초기 15문항 수록**:
  * 명화 5선(모나리자, 별이 빛나는 밤, 진주 귀걸이를 한 소녀, 절규, 해바라기)
  * 게임 캐릭터 5선(피카츄, 마리오, 커비, 크리퍼, 티모)
  * 애니 캐릭터 5선(도라에몽, 짱구, 아냐 포저, 카마도 탄지로, 토토로)

## 2. 폴더 구조
* `primary_data/` : 원본 참조 이미지 데이터 (변경 불가능한 원시 데이터)
* `secondary_data/` : 다중 스케일 오차 최소화 알고리즘으로 생성된 문항별 추상화 SVG (`svg_quiz_` 접두사)
* `intermediate_results/` : 도형 수에 따른 RMSE 수렴 측정치(`rmse_convergence.csv`) 및 엔진 검증 결과(`engine_verification_results.csv`, `utf-8-sig` 인코딩)
* `visualizations/` : 14문항 추상화 생성 결과 비교 이미지(`quiz_14_primitive_results.png`)
* `interim_reports/` : 분석 방법론, 가정 검증, 한계 및 결과를 기록한 중간 보고서
  * `interim_reports/01_initial_implementation_report.md` : 1차 설계, 도형 분해 검증 및 멀티플레이 배포 보고서
  * `interim_reports/02_custom_image_and_polygon_scaling_analysis.md` : 커스텀 이미지 추가 및 삼각형 개수 확장에 관한 기술·수치 분석 보고서
* `docs/` : 프로젝트 기획 및 설계 문서
  * `docs/구현계획서.md` : 1차 기본 시스템 구현 계획 및 아키텍처 명세
  * `docs/추가기능_계획서_이미지추가_및_삼각형확장.md` : 커스텀 이미지 추가 및 삼각형 개수 조절 기능 상세 설계 계획서
* `scripts/` : 데이터셋 생성(`01_build_quiz_dataset.py`) 및 엔진 검증(`02_verify_quiz_engine.py`) 스크립트
* `pdfs/` : 관련 레퍼런스 문서 보관 폴더
* `data/` : 웹 클라이언트용 문제 데이터 번들(`questions.js`)
* `js/` : 규칙 엔진(`engine.js`), 네트워크 및 비밀번호 인증(`net.js`), 화면 제어(`app.js`)

## 3. 로컬 실행 및 검증 방법
정적 파일 서버를 띄워 브라우저에서 바로 실행할 수 있습니다.
```powershell
python -m http.server 8795
```
브라우저에서 `http://localhost:8795`에 접속합니다.

엔진 단위 시험 및 문법 검증은 다음 스크립트로 실행합니다.
```powershell
python scripts/02_verify_quiz_engine.py
```
