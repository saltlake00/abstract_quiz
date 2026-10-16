// -*- coding: utf-8 -*-
/**
 * app.js
 * 추상화 그림맞추기 온라인 메인 클라이언트 컨트롤러
 * - 모두가 같은 화면(추상화 SVG + 타이머/힌트 + 실시간 채팅 + 점수판)을 공유
 * - 방 생성 및 비밀번호 설정/검증, 초대 링크(?room=코드) 자동 인식
 * - 한글 조합(isComposing) 안전 처리 및 스포일러 방지 정답 판정
 */

(function () {
  "use strict";

  const QUESTIONS = window.QUIZ_QUESTIONS || [];

  // 로컬 상태
  let net = null;
  let isComposing = false;
  let animFrameId = null;
  let hostTickTimer = null;
  let nextRoundTimer = null;

  // 방 공유 상태 (호스트가 정본을 유지하고 STATE_SYNC로 전파)
  let roomState = {
    roomCode: "",
    hasPassword: false,
    phase: "lobby", // lobby | countdown | playing | round_result | final_result
    settings: {
      category: "전체",
      totalRounds: 5,
      durationSec: 30,
      allowTypo: true,
    },
    players: {}, // uid -> { uid, nick, isHost, ready, score, solvedCount, roundSolved, roundRank, roundGain }
    roundIndex: 0,
    questionOrder: [], // question id 배열
    currentQuestionId: null,
    roundStartAt: 0,
    elapsedMs: 0,
    countdownSec: 3,
    solvedOrder: [], // 이번 라운드 정답자 uid 배열
    chats: [], // 최근 채팅/시스템 메시지 배열 (최대 60개)
  };

  // 현재 렌더링 중인 SVG 폴리곤 요소 캐시
  let activeQuestionId = null;
  let activePolygonEls = [];

  // DOM 참조 헬퍼
  const $ = (id) => document.getElementById(id);

  function init() {
    // 저장된 닉네임 복원
    const savedNick = localStorage.getItem("aq_nick") || "";
    if (savedNick) {
      $("create-nick").value = savedNick;
      $("join-nick").value = savedNick;
    }

    // 초기 방 코드 생성
    $("create-room-code").value = window.QuizEngine.generateRoomCode(5);

    // URL 파라미터 (?room=XXXX) 확인
    const params = new URLSearchParams(window.location.search);
    const roomParam = params.get("room");
    if (roomParam) {
      $("join-room-code").value = roomParam.toUpperCase().trim();
      switchHomeTab("join");
    }

    bindEvents();
  }

  function switchHomeTab(tab) {
    document.querySelectorAll(".tab-btn").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.tab === tab);
    });
    $("panel-create").classList.toggle("hidden", tab !== "create");
    $("panel-join").classList.toggle("hidden", tab !== "join");
  }

  function bindEvents() {
    // 홈 탭 전환
    document.querySelectorAll(".tab-btn").forEach((btn) => {
      btn.addEventListener("click", () => switchHomeTab(btn.dataset.tab));
    });

    // 방 코드 새로고침
    $("btn-regen-code").addEventListener("click", () => {
      $("create-room-code").value = window.QuizEngine.generateRoomCode(5);
    });

    // 비밀번호 안내 표시 업데이트
    $("create-password").addEventListener("input", (e) => {
      const hasPw = e.target.value.trim().length > 0;
      const badge = $("pw-status-hint");
      if (hasPw) {
        badge.textContent = "🔒 비공개 방 (비밀번호를 아는 사람만 입장)";
        badge.className = "pw-hint locked";
      } else {
        badge.textContent = "🌐 공개 방 (방 코드만으로 즉시 입장)";
        badge.className = "pw-hint open";
      }
    });

    // 방 만들기 실행
    $("form-create").addEventListener("submit", (e) => {
      e.preventDefault();
      handleCreateRoom();
    });

    // 방 참가하기 실행
    $("form-join").addEventListener("submit", (e) => {
      e.preventDefault();
      handleJoinRoom();
    });

    // 혼자 바로 연습하기 버튼
    $("btn-solo-start").addEventListener("click", () => {
      if (!$("create-nick").value.trim()) {
        $("create-nick").value = "예술탐정";
      }
      handleCreateRoom(true);
    });

    // 대기실 컨트롤
    $("btn-ready").addEventListener("click", () => {
      if (!net) return;
      net.sendToHost({ type: "TOGGLE_READY" });
    });

    $("btn-start-game").addEventListener("click", () => {
      if (!net || !net.isHost) return;
      hostStartGame();
    });

    $("btn-next-round").addEventListener("click", () => {
      if (!net || !net.isHost) return;
      hostAdvanceRound();
    });

    $("btn-back-lobby").addEventListener("click", () => {
      if (!net || !net.isHost) return;
      hostReturnToLobby();
    });

    // 대기실 방장 설정 변경
    ["lobby-category", "lobby-rounds", "lobby-duration"].forEach((id) => {
      const el = $(id);
      if (!el) return;
      el.addEventListener("change", () => {
        if (!net || !net.isHost || roomState.phase !== "lobby") return;
        roomState.settings.category = $("lobby-category").value;
        roomState.settings.totalRounds = parseInt($("lobby-rounds").value, 10) || 5;
        roomState.settings.durationSec = parseInt($("lobby-duration").value, 10) || 30;
        syncStateFromHost();
      });
    });

    // 초대 링크 복사
    $("btn-copy-link").addEventListener("click", () => {
      const url = new URL(window.location.href);
      url.searchParams.set("room", roomState.roomCode);
      navigator.clipboard.writeText(url.toString()).then(() => {
        showToast("초대 링크가 복사되었습니다! 단톡방에 공유해 보세요.");
      }).catch(() => {
        showToast("방 코드: " + roomState.roomCode);
      });
    });

    // 멀티 테스트용 게스트 새 창 열기
    $("btn-open-guest-tab").addEventListener("click", () => {
      const url = new URL(window.location.href);
      url.searchParams.set("room", roomState.roomCode);
      window.open(url.toString(), "_blank");
    });

    // 방 나가기
    $("btn-leave-room").addEventListener("click", () => {
      leaveRoom();
    });

    // 채팅 및 정답 입력 (한국어 IME 조합 안전 처리)
    const chatInput = $("chat-input");
    chatInput.addEventListener("compositionstart", () => {
      isComposing = true;
    });
    chatInput.addEventListener("compositionend", () => {
      isComposing = false;
    });
    chatInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        if (e.isComposing || isComposing || e.keyCode === 229) return;
        e.preventDefault();
        submitChatOrAnswer();
      }
    });
    $("btn-send-chat").addEventListener("click", () => {
      submitChatOrAnswer();
    });

    // Firebase 선택 설정 모달
    $("btn-open-config").addEventListener("click", () => {
      $("config-fb-url").value = localStorage.getItem("aq_firebase_url") || "";
      $("modal-config").classList.remove("hidden");
    });
    $("btn-close-config").addEventListener("click", () => {
      $("modal-config").classList.add("hidden");
    });
    $("btn-save-config").addEventListener("click", () => {
      const url = $("config-fb-url").value.trim();
      if (url) {
        localStorage.setItem("aq_firebase_url", url.replace(/\/+$/, ""));
        showToast("Firebase DB 주소가 저장되었습니다.");
      } else {
        localStorage.removeItem("aq_firebase_url");
        showToast("기본 무료 클라우드(WebRTC + 로컬 채널) 모드로 설정되었습니다.");
      }
      $("modal-config").classList.add("hidden");
    });
  }

  function createNetworkInstance() {
    return new window.RoomNetwork({
      onStatus: ({ mode, text }) => {
        const el = $("net-status");
        if (el) {
          el.textContent = text;
          el.dataset.mode = mode;
        }
      },
      onError: (msg) => {
        showHomeAlert(msg);
        showToast(msg);
      },
      onHostReady: ({ roomCode, hasPassword, hostId, nick }) => {
        enterRoomScreen();
        addSystemChat(
          hasPassword
            ? `🔒 방 [${roomCode}]이 생성되었습니다. (비밀번호 보호 활성화)`
            : `🌐 방 [${roomCode}]이 생성되었습니다. 친구들을 초대해 보세요!`
        );
        syncStateFromHost();
      },
      onJoinRequest: ({ uid, nick }) => {
        // 닉네임 중복 방지 처리
        let cleanNick = (nick || "참가자").trim().slice(0, 12);
        const existingNicks = Object.values(roomState.players)
          .filter((p) => p.uid !== uid)
          .map((p) => p.nick);
        if (existingNicks.includes(cleanNick)) {
          let suffix = 2;
          while (existingNicks.includes(`${cleanNick}${suffix}`)) suffix++;
          cleanNick = `${cleanNick}${suffix}`;
        }

        const isReconnect = Boolean(roomState.players[uid]);
        if (!isReconnect) {
          roomState.players[uid] = {
            uid,
            nick: cleanNick,
            isHost: false,
            ready: false,
            score: 0,
            solvedCount: 0,
            roundSolved: false,
            roundRank: null,
            roundGain: 0,
          };
          addSystemChat(`👋 ${cleanNick}님이 입장했습니다.`);
        } else {
          roomState.players[uid].nick = cleanNick;
          addSystemChat(`🔄 ${cleanNick}님이 재접속했습니다.`);
        }

        setTimeout(() => syncStateFromHost(), 30);
        return { ok: true, state: sanitizeStateForSync() };
      },
      onPeerLeave: (uid) => {
        const p = roomState.players[uid];
        if (p) {
          addSystemChat(`🚪 ${p.nick}님의 연결이 끊어졌습니다.`);
          delete roomState.players[uid];
          syncStateFromHost();
        }
      },
      onHostMessage: (msg) => {
        handleMessageOnHost(msg);
      },
      onAuthOk: (data) => {
        hideHomeAlert();
        if (data.state) {
          applySyncedState(data.state);
        }
        enterRoomScreen();
        showToast(`방 [${data.roomCode}]에 입장했습니다!`);
      },
      onAuthFail: (data) => {
        showHomeAlert(data.reason || "입장에 실패했습니다.");
        if (data.needPassword) {
          const pwEl = $("join-password");
          pwEl.focus();
          pwEl.classList.add("input-error");
        }
      },
      onGuestMessage: (data) => {
        if (data.type === "STATE_SYNC" && data.state) {
          applySyncedState(data.state);
        }
      },
    });
  }

  function handleCreateRoom(autoStart = false) {
    hideHomeAlert();
    const nick = $("create-nick").value.trim() || "방장";
    const roomCode = ($("create-room-code").value.trim() || window.QuizEngine.generateRoomCode(5)).toUpperCase();
    const password = $("create-password").value.trim();
    const category = $("create-category").value;
    const totalRounds = parseInt($("create-rounds").value, 10) || 5;
    const durationSec = parseInt($("create-duration").value, 10) || 30;

    localStorage.setItem("aq_nick", nick);

    net = createNetworkInstance();
    const myId = net.myId;

    roomState = {
      roomCode,
      hasPassword: Boolean(password),
      phase: "lobby",
      settings: {
        category,
        totalRounds,
        durationSec,
        allowTypo: true,
      },
      players: {
        [myId]: {
          uid: myId,
          nick,
          isHost: true,
          ready: true,
          score: 0,
          solvedCount: 0,
          roundSolved: false,
          roundRank: null,
          roundGain: 0,
        },
      },
      roundIndex: 0,
      questionOrder: [],
      currentQuestionId: null,
      roundStartAt: 0,
      elapsedMs: 0,
      countdownSec: 3,
      solvedOrder: [],
      chats: [],
    };

    net.createRoom({ roomCode, nick, password });

    if (autoStart) {
      setTimeout(() => {
        if (net && net.isHost && roomState.phase === "lobby") {
          hostStartGame();
        }
      }, 250);
    }
  }

  function handleJoinRoom() {
    hideHomeAlert();
    $("join-password").classList.remove("input-error");
    const nick = $("join-nick").value.trim();
    const roomCode = $("join-room-code").value.trim().toUpperCase();
    const password = $("join-password").value.trim();

    if (!nick) {
      showHomeAlert("닉네임을 입력해 주세요.");
      $("join-nick").focus();
      return;
    }
    if (!roomCode) {
      showHomeAlert("입장할 방 코드를 입력해 주세요.");
      $("join-room-code").focus();
      return;
    }

    localStorage.setItem("aq_nick", nick);
    showHomeAlert("방 호스트에 연결 및 비밀번호 확인 중입니다...", "info");

    net = createNetworkInstance();
    net.joinRoom({ roomCode, nick, password });
  }

  function leaveRoom() {
    stopAllTimers();
    if (net) {
      net.disconnect();
      net = null;
    }
    $("screen-room").classList.add("hidden");
    $("screen-home").classList.remove("hidden");
  }

  function enterRoomScreen() {
    $("screen-home").classList.add("hidden");
    $("screen-room").classList.remove("hidden");
    renderRoomUI();
    startClientRenderLoop();
  }

  /**
   * 호스트에서 참가자들의 액션(레디 토글, 채팅/정답 제출)을 처리한다.
   */
  function handleMessageOnHost(msg) {
    if (!net || !net.isHost || !msg) return;
    const player = roomState.players[msg.uid];
    if (!player) return;

    if (msg.type === "TOGGLE_READY") {
      if (roomState.phase !== "lobby") return;
      player.ready = !player.ready;
      syncStateFromHost();
      return;
    }

    if (msg.type === "CHAT_SUBMIT") {
      const text = (msg.text || "").trim().slice(0, 80);
      if (!text) return;

      // 라운드 진행 중이면 정답 여부 먼저 판정
      if (roomState.phase === "playing" && roomState.currentQuestionId) {
        const q = getQuestionById(roomState.currentQuestionId);
        if (q) {
          const isMatch = window.QuizEngine.checkAnswer(
            text,
            q.answers,
            roomState.settings.allowTypo
          );

          // 이미 정답을 맞힌 사람이 정답 단어를 또 치면 스포일러 방지
          if (player.roundSolved) {
            if (isMatch) {
              addChatItem({
                kind: "system",
                text: `🤫 ${player.nick}님, 이미 정답을 맞히셨습니다! (정답 스포일러 자동 가림)`,
              });
            } else {
              addChatItem({
                kind: "chat",
                nick: `${player.nick} (정답자)`,
                text,
              });
            }
            syncStateFromHost();
            return;
          }

          if (isMatch) {
            // 정답 처리!
            const elapsed = Date.now() - roomState.roundStartAt;
            const durMs = roomState.settings.durationSec * 1000;
            const totalPolys = q.polygons.length;
            const k = window.QuizEngine.computeVisibleCount(elapsed, durMs, totalPolys);
            const rankIdx = roomState.solvedOrder.length;
            const scoreObj = window.QuizEngine.calculateScore(k, totalPolys, rankIdx);

            player.roundSolved = true;
            player.roundRank = rankIdx + 1;
            player.roundGain = scoreObj.total;
            player.score += scoreObj.total;
            player.solvedCount = (player.solvedCount || 0) + 1;
            roomState.solvedOrder.push(player.uid);

            const secStr = (Math.min(elapsed, durMs) / 1000).toFixed(1);
            const rankLabel = rankIdx === 0 ? "🥇 1등 정답!" : rankIdx === 1 ? "🥈 2등 정답!" : rankIdx === 2 ? "🥉 3등 정답!" : "🎉 정답!";
            addChatItem({
              kind: "correct",
              nick: player.nick,
              text: `${rankLabel} ${player.nick}님이 도형 ${k}개(${secStr}초)에서 맞혔습니다! (+${scoreObj.total}점)`,
            });

            // 모든 참가자가 정답을 맞혔는지 확인
            const allPlayers = Object.values(roomState.players);
            const allSolved = allPlayers.every((p) => p.roundSolved);
            if (allSolved) {
              hostFinishRound("전원 정답 달성!");
            } else {
              syncStateFromHost();
            }
            return;
          }
        }
      }

      // 오답 또는 일반 채팅은 그대로 전원에게 공개
      addChatItem({
        kind: roomState.phase === "playing" ? "wrong" : "chat",
        nick: player.nick,
        text,
      });
      syncStateFromHost();
    }
  }

  function hostStartGame() {
    if (!net || !net.isHost) return;
    stopAllTimers();

    // 카테고리 필터링 및 셔플
    const cat = roomState.settings.category;
    let pool = QUESTIONS.filter((q) => cat === "전체" || q.category === cat);
    if (pool.length === 0) pool = QUESTIONS.slice();

    // Fisher-Yates 셔플
    const shuffled = pool.slice();
    for (let i = shuffled.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [shuffled[i], shuffled[j]] = [shuffled[j], shuffled[i]];
    }

    const count = Math.min(roomState.settings.totalRounds, shuffled.length);
    roomState.questionOrder = shuffled.slice(0, count).map((q) => q.id);
    roomState.roundIndex = 0;

    // 점수 초기화
    Object.values(roomState.players).forEach((p) => {
      p.score = 0;
      p.solvedCount = 0;
      p.roundSolved = false;
      p.roundRank = null;
      p.roundGain = 0;
    });

    addSystemChat(
      `🚀 게임을 시작합니다! (${roomState.settings.category} · 총 ${count}라운드 · 제한시간 ${roomState.settings.durationSec}초)`
    );

    hostStartCountdown();
  }

  function hostStartCountdown() {
    stopAllTimers();
    roomState.phase = "countdown";
    roomState.countdownSec = 3;
    roomState.currentQuestionId = roomState.questionOrder[roomState.roundIndex];
    roomState.solvedOrder = [];
    Object.values(roomState.players).forEach((p) => {
      p.roundSolved = false;
      p.roundRank = null;
      p.roundGain = 0;
    });
    syncStateFromHost();

    hostTickTimer = setInterval(() => {
      roomState.countdownSec -= 1;
      if (roomState.countdownSec <= 0) {
        clearInterval(hostTickTimer);
        hostTickTimer = null;
        hostBeginPlayingRound();
      } else {
        syncStateFromHost();
      }
    }, 900);
  }

  function hostBeginPlayingRound() {
    roomState.phase = "playing";
    roomState.roundStartAt = Date.now();
    roomState.elapsedMs = 0;
    const q = getQuestionById(roomState.currentQuestionId);
    addSystemChat(
      `🎨 [Round ${roomState.roundIndex + 1}/${roomState.questionOrder.length}] 분야: ${q ? q.category : ""} — 추상화가 그려지기 시작합니다!`
    );
    syncStateFromHost();

    const durMs = roomState.settings.durationSec * 1000;
    hostTickTimer = setInterval(() => {
      if (roomState.phase !== "playing") return;
      roomState.elapsedMs = Date.now() - roomState.roundStartAt;
      if (roomState.elapsedMs >= durMs) {
        roomState.elapsedMs = durMs;
        hostFinishRound("⏰ 제한 시간이 종료되었습니다!");
      } else {
        syncStateFromHost();
      }
    }, 400);
  }

  function hostFinishRound(reasonText) {
    if (hostTickTimer) {
      clearInterval(hostTickTimer);
      hostTickTimer = null;
    }
    roomState.phase = "round_result";
    roomState.elapsedMs = roomState.settings.durationSec * 1000;
    const q = getQuestionById(roomState.currentQuestionId);
    if (q) {
      addSystemChat(`${reasonText} 정답은 【${q.title}】 입니다!`);
    }
    syncStateFromHost();

    // 5.5초 후 자동으로 다음 라운드 또는 최종 결과로 이동
    if (nextRoundTimer) clearTimeout(nextRoundTimer);
    nextRoundTimer = setTimeout(() => {
      if (roomState.phase === "round_result" && net && net.isHost) {
        hostAdvanceRound();
      }
    }, 5500);
  }

  function hostAdvanceRound() {
    if (nextRoundTimer) {
      clearTimeout(nextRoundTimer);
      nextRoundTimer = null;
    }
    if (roomState.roundIndex + 1 < roomState.questionOrder.length) {
      roomState.roundIndex += 1;
      hostStartCountdown();
    } else {
      roomState.phase = "final_result";
      addSystemChat("🏁 모든 라운드가 종료되었습니다! 최종 순위를 확인하세요.");
      syncStateFromHost();
    }
  }

  function hostReturnToLobby() {
    stopAllTimers();
    roomState.phase = "lobby";
    roomState.currentQuestionId = null;
    roomState.elapsedMs = 0;
    syncStateFromHost();
  }

  function stopAllTimers() {
    if (hostTickTimer) {
      clearInterval(hostTickTimer);
      hostTickTimer = null;
    }
    if (nextRoundTimer) {
      clearTimeout(nextRoundTimer);
      nextRoundTimer = null;
    }
  }

  function addSystemChat(text) {
    addChatItem({ kind: "system", text });
  }

  function addChatItem(item) {
    roomState.chats.push({
      id: "c_" + Date.now() + "_" + Math.random().toString(36).slice(2, 6),
      kind: item.kind || "chat",
      nick: item.nick || "",
      text: item.text || "",
      ts: Date.now(),
    });
    if (roomState.chats.length > 60) {
      roomState.chats = roomState.chats.slice(-60);
    }
  }

  function sanitizeStateForSync() {
    return JSON.parse(JSON.stringify(roomState));
  }

  function syncStateFromHost() {
    if (!net || !net.isHost) return;
    const snap = sanitizeStateForSync();
    net.broadcastFromHost({
      type: "STATE_SYNC",
      state: snap,
    });
    renderRoomUI();
  }

  function applySyncedState(newState) {
    const prevPhase = roomState.phase;
    const prevQ = roomState.currentQuestionId;
    roomState = newState;

    // 게스트의 로컬 보간 타이머를 위해 기준 시각 동기화
    if (roomState.phase === "playing") {
      roomState._localSyncAt = performance.now();
      roomState._baseElapsedMs = roomState.elapsedMs || 0;
    }
    if (prevPhase !== roomState.phase || prevQ !== roomState.currentQuestionId) {
      activeQuestionId = null;
    }
    renderRoomUI();
  }

  function submitChatOrAnswer() {
    const input = $("chat-input");
    const text = input.value.trim();
    if (!text || !net) return;
    input.value = "";
    net.sendToHost({
      type: "CHAT_SUBMIT",
      text,
    });
  }

  function getQuestionById(qid) {
    return QUESTIONS.find((q) => q.id === qid) || null;
  }

  /**
   * 화면 전체 UI 상태를 roomState 기준으로 갱신한다.
   */
  function renderRoomUI() {
    if (!net) return;

    // 상단 방 정보 헤더
    $("room-code-display").textContent = roomState.roomCode;
    const pwBadge = $("room-pw-badge");
    if (roomState.hasPassword) {
      pwBadge.textContent = "🔒 비공개방";
      pwBadge.className = "badge badge-lock";
    } else {
      pwBadge.textContent = "🌐 공개방";
      pwBadge.className = "badge badge-open";
    }

    // 단계별 스테이지 뷰 전환
    const phase = roomState.phase;
    $("stage-lobby").classList.toggle("hidden", phase !== "lobby");
    $("stage-countdown").classList.toggle("hidden", phase !== "countdown");
    $("stage-game").classList.toggle("hidden", phase !== "playing" && phase !== "round_result");
    $("stage-final").classList.toggle("hidden", phase !== "final_result");

    if (phase === "lobby") {
      renderLobbyStage();
    } else if (phase === "countdown") {
      renderCountdownStage();
    } else if (phase === "playing" || phase === "round_result") {
      renderGameStage();
    } else if (phase === "final_result") {
      renderFinalStage();
    }

    renderScoreboard();
    renderChatLog();
  }

  function renderLobbyStage() {
    const isHost = net && net.isHost;
    $("lobby-category").value = roomState.settings.category;
    $("lobby-rounds").value = String(roomState.settings.totalRounds);
    $("lobby-duration").value = String(roomState.settings.durationSec);

    ["lobby-category", "lobby-rounds", "lobby-duration"].forEach((id) => {
      $(id).disabled = !isHost;
    });

    // 참가자 카드 목록
    const players = Object.values(roomState.players);
    const listEl = $("lobby-player-list");
    listEl.innerHTML = players
      .map((p) => {
        const isMe = net && p.uid === net.myId;
        const roleBadge = p.isHost ? '<span class="role-tag host">👑 방장</span>' : '<span class="role-tag guest">참가자</span>';
        const readyBadge = p.isHost || p.ready
          ? '<span class="ready-tag on">준비 완료</span>'
          : '<span class="ready-tag off">대기중</span>';
        return `
          <div class="lobby-player-card ${isMe ? "me" : ""}">
            <div class="lp-top">
              <strong>${escapeHtml(p.nick)}${isMe ? " (나)" : ""}</strong>
              ${roleBadge}
            </div>
            <div class="lp-bottom">
              ${readyBadge}
              <span class="lp-score">${p.score}점</span>
            </div>
          </div>
        `;
      })
      .join("");

    // 버튼 표시
    $("btn-start-game").classList.toggle("hidden", !isHost);
    $("btn-ready").classList.toggle("hidden", isHost);
    if (!isHost && net && roomState.players[net.myId]) {
      const meReady = roomState.players[net.myId].ready;
      $("btn-ready").textContent = meReady ? "준비 취소" : "준비 완료 (Ready)";
      $("btn-ready").classList.toggle("ready-active", meReady);
    }
  }

  function renderCountdownStage() {
    const q = getQuestionById(roomState.currentQuestionId);
    $("cd-round-label").textContent = `ROUND ${roomState.roundIndex + 1} / ${roomState.questionOrder.length}`;
    $("cd-category-label").textContent = q ? `분야: ${q.category}` : "";
    $("cd-number").textContent = roomState.countdownSec;
  }

  function ensureSvgMounted(q) {
    if (!q) return;
    if (activeQuestionId === q.id && activePolygonEls.length === q.polygons.length) {
      return;
    }
    activeQuestionId = q.id;
    const container = $("svg-canvas-wrap");
    const scaleAttr = q.scale && q.scale !== 1 ? `transform="scale(${q.scale}) translate(0.5 0.5)"` : "";
    const polysHtml = q.polygons
      .map(
        (p) =>
          `<polygon fill="${p.fill}" fill-opacity="${p.opacity}" points="${p.points}" style="display:none" />`
      )
      .join("");

    container.innerHTML = `
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${q.width} ${q.height}">
        <rect x="0" y="0" width="${q.width}" height="${q.height}" fill="${q.bg}" />
        <g ${scaleAttr}>${polysHtml}</g>
      </svg>
    `;
    activePolygonEls = Array.from(container.querySelectorAll("polygon"));
  }

  function renderGameStage() {
    const q = getQuestionById(roomState.currentQuestionId);
    if (!q) return;

    ensureSvgMounted(q);

    $("game-round-badge").textContent = `ROUND ${roomState.roundIndex + 1} / ${roomState.questionOrder.length}`;
    $("game-cat-badge").textContent = q.category;

    const isResult = roomState.phase === "round_result";
    const banner = $("round-answer-banner");
    if (isResult) {
      banner.classList.remove("hidden");
      $("answer-title").textContent = `정답: ${q.title}`;
      $("answer-desc").textContent = q.desc || "";
      $("btn-next-round").classList.toggle("hidden", !(net && net.isHost));
      // 전체 도형 모두 표시
      updateVisiblePolygons(q.polygons.length, q.polygons.length, roomState.settings.durationSec * 1000);
    } else {
      banner.classList.add("hidden");
    }
  }

  function updateVisiblePolygons(k, totalPolys, elapsedMs) {
    for (let i = 0; i < activePolygonEls.length; i++) {
      activePolygonEls[i].style.display = i < k ? "" : "none";
    }
    const durMs = roomState.settings.durationSec * 1000;
    const sec = Math.min(durMs, Math.max(0, elapsedMs)) / 1000;
    $("stat-shapes").textContent = `도형 ${k} / ${totalPolys}`;
    $("stat-time").textContent = `${sec.toFixed(1)}s / ${roomState.settings.durationSec}s`;

    const scorePreview = window.QuizEngine.calculateScore(k, totalPolys, roomState.solvedOrder.length);
    $("stat-potential").textContent = `지금 맞히면 +${scorePreview.total}점`;

    const pct = Math.min(100, (elapsedMs / durMs) * 100);
    $("time-progress-fill").style.width = `${pct.toFixed(1)}%`;

    // 단계별 힌트 표시
    const q = getQuestionById(roomState.currentQuestionId);
    const hintBox = $("hint-bar");
    if (!q) return;
    if (roomState.phase === "round_result") {
      hintBox.textContent = `💡 정답 공개: ${q.title} (${q.desc})`;
      hintBox.className = "hint-bar revealed";
    } else if (pct >= 72) {
      hintBox.textContent = `💡 2단계 힌트: ${q.hint1} · [${q.hint2}]`;
      hintBox.className = "hint-bar active-2";
    } else if (pct >= 42) {
      hintBox.textContent = `💡 1단계 힌트: ${q.hint1}`;
      hintBox.className = "hint-bar active-1";
    } else {
      hintBox.textContent = "🎨 도형이 쌓이며 추상화가 구체화됩니다. 채팅창에 정답을 입력해 보세요!";
      hintBox.className = "hint-bar";
    }
  }

  function startClientRenderLoop() {
    if (animFrameId) cancelAnimationFrame(animFrameId);

    function frame() {
      if (roomState.phase === "playing" && roomState.currentQuestionId) {
        const q = getQuestionById(roomState.currentQuestionId);
        if (q) {
          ensureSvgMounted(q);
          const durMs = roomState.settings.durationSec * 1000;
          let currentElapsed = roomState.elapsedMs;
          if (net && net.isHost) {
            currentElapsed = Date.now() - roomState.roundStartAt;
          } else if (roomState._localSyncAt) {
            currentElapsed = roomState._baseElapsedMs + (performance.now() - roomState._localSyncAt);
          }
          currentElapsed = Math.min(durMs, Math.max(0, currentElapsed));
          const k = window.QuizEngine.computeVisibleCount(
            currentElapsed,
            durMs,
            q.polygons.length
          );
          updateVisiblePolygons(k, q.polygons.length, currentElapsed);
        }
      }
      animFrameId = requestAnimationFrame(frame);
    }

    animFrameId = requestAnimationFrame(frame);
  }

  function renderFinalStage() {
    const sorted = Object.values(roomState.players).sort((a, b) => b.score - a.score);
    const listEl = $("final-ranking-list");
    listEl.innerHTML = sorted
      .map((p, idx) => {
        const medal = idx === 0 ? "🥇 1위" : idx === 1 ? "🥈 2위" : idx === 2 ? "🥉 3위" : `${idx + 1}위`;
        const isLast = sorted.length > 1 && idx === sorted.length - 1;
        const penaltyBadge = isLast ? '<span class="penalty-tag">🥒 벌칙: 피클팝 당첨!</span>' : "";
        return `
          <div class="final-rank-row ${idx === 0 ? "winner" : ""}">
            <span class="fr-rank">${medal}</span>
            <span class="fr-nick">${escapeHtml(p.nick)} ${penaltyBadge}</span>
            <span class="fr-solved">${p.solvedCount || 0}문제 정답</span>
            <strong class="fr-score">${p.score}점</strong>
          </div>
        `;
      })
      .join("");

    $("btn-back-lobby").classList.toggle("hidden", !(net && net.isHost));
  }

  function renderScoreboard() {
    const sorted = Object.values(roomState.players).sort((a, b) => b.score - a.score);
    const boardEl = $("live-scoreboard");
    boardEl.innerHTML = sorted
      .map((p, idx) => {
        const isMe = net && p.uid === net.myId;
        const solvedBadge = p.roundSolved
          ? `<span class="sb-solved">✅ +${p.roundGain}</span>`
          : "";
        return `
          <div class="sb-row ${isMe ? "me" : ""} ${p.roundSolved ? "solved" : ""}">
            <span class="sb-rank">#${idx + 1}</span>
            <span class="sb-nick">${escapeHtml(p.nick)}${p.isHost ? " 👑" : ""}</span>
            ${solvedBadge}
            <strong class="sb-score">${p.score}점</strong>
          </div>
        `;
      })
      .join("");
  }

  let lastRenderedChatId = null;
  function renderChatLog() {
    const chats = roomState.chats || [];
    const lastId = chats.length > 0 ? chats[chats.length - 1].id : null;
    if (lastId === lastRenderedChatId && $("chat-log").children.length === chats.length) {
      return;
    }
    lastRenderedChatId = lastId;

    const logEl = $("chat-log");
    logEl.innerHTML = chats
      .map((c) => {
        if (c.kind === "system") {
          return `<div class="chat-msg system">${escapeHtml(c.text)}</div>`;
        }
        if (c.kind === "correct") {
          return `<div class="chat-msg correct">${escapeHtml(c.text)}</div>`;
        }
        if (c.kind === "wrong") {
          return `<div class="chat-msg wrong"><span class="chat-nick">${escapeHtml(c.nick)}:</span> ${escapeHtml(c.text)}</div>`;
        }
        return `<div class="chat-msg normal"><span class="chat-nick">${escapeHtml(c.nick)}:</span> ${escapeHtml(c.text)}</div>`;
      })
      .join("");
    logEl.scrollTop = logEl.scrollHeight;
  }

  function showHomeAlert(msg, type = "error") {
    const el = $("home-alert");
    el.textContent = msg;
    el.className = `alert-box ${type}`;
    el.classList.remove("hidden");
  }

  function hideHomeAlert() {
    $("home-alert").classList.add("hidden");
  }

  let toastTimer = null;
  function showToast(msg) {
    const el = $("toast");
    el.textContent = msg;
    el.classList.remove("hidden");
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      el.classList.add("hidden");
    }, 3200);
  }

  function escapeHtml(str) {
    return String(str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  document.addEventListener("DOMContentLoaded", init);
})();
