// -*- coding: utf-8 -*-
/**
 * net.js
 * 추상화 그림맞추기 온라인 실시간 멀티플레이 네트워크 어댑터
 *
 * 지원 채널:
 * 1. PeerJS (WebRTC 무료 클라우드 브로커) : 별도 가입·키 없이 다른 기기/네트워크 간 실시간 연결
 * 2. BroadcastChannel : 동일 기기 내 다중 브라우저 탭 간 0ms 즉시 동기화 (항상 병행 작동)
 * 3. Firebase Realtime Database (선택 설정) : 설정 모달에 databaseURL 입력 시 REST/폴링 동기화 병행
 *
 * 보안 및 방 관리:
 * - 호스트 권위(Authoritative Host) 구조
 * - 방 비밀번호 해시(hashRoomPassword) 대조를 통한 입장 승인(AUTH_OK) / 거부(AUTH_FAIL)
 */

(function (global) {
  "use strict";

  const PEER_PREFIX = "aq_quiz_v1_room_";
  const BC_PREFIX = "aq_quiz_bc_";

  class RoomNetwork {
    constructor(callbacks = {}) {
      this.callbacks = callbacks;
      this.isHost = false;
      this.roomCode = "";
      this.passwordHash = "";
      this.hasPassword = false;
      this.myId = this._loadOrCreateClientId();
      this.myNick = "";

      this.peer = null;
      this.hostConn = null;
      this.guestConns = new Map(); // peerId -> DataConnection
      this.bc = null;
      this.fbUrl = localStorage.getItem("aq_firebase_url") || "";
      this.fbPollTimer = null;
      this.connected = false;
    }

    _loadOrCreateClientId() {
      let id = sessionStorage.getItem("aq_client_id");
      if (!id) {
        id = "u_" + Math.random().toString(36).slice(2, 10) + "_" + Date.now().toString(36).slice(-4);
        sessionStorage.setItem("aq_client_id", id);
      }
      return id;
    }

    setFirebaseUrl(url) {
      this.fbUrl = (url || "").trim().replace(/\/+$/, "");
      if (this.fbUrl) {
        localStorage.setItem("aq_firebase_url", this.fbUrl);
      } else {
        localStorage.removeItem("aq_firebase_url");
      }
    }

    /**
     * 호스트로서 새 방을 생성한다.
     */
    createRoom({ roomCode, nick, password }) {
      this.disconnect();
      this.isHost = true;
      this.roomCode = String(roomCode).toUpperCase().trim();
      this.myNick = nick.trim();
      this.passwordHash = global.QuizEngine.hashRoomPassword(password, this.roomCode);
      this.hasPassword = Boolean(this.passwordHash);

      // 1. 로컬 다중 탭 BroadcastChannel 오픈
      this._initBroadcastChannel();

      // 2. 선택적 Firebase 방 메타 등록
      if (this.fbUrl) {
        this._fbPut(`/rooms/${this.roomCode}/meta.json`, {
          roomCode: this.roomCode,
          hasPassword: this.hasPassword,
          hostId: this.myId,
          createdAt: Date.now(),
        });
        this._startFirebasePolling();
      }

      // 3. PeerJS 클라우드 브로커에 방 ID 등록
      if (typeof global.Peer !== "undefined") {
        const peerId = PEER_PREFIX + this.roomCode;
        try {
          this.peer = new global.Peer(peerId, {
            debug: 1,
            config: {
              iceServers: [
                { urls: "stun:stun.l.google.com:19302" },
                { urls: "stun:stun1.l.google.com:19302" },
              ],
            },
          });

          this.peer.on("open", () => {
            this.connected = true;
            this._emitStatus("online", "온라인 방 개설 완료 (WebRTC + 로컬 채널 활성화)");
          });

          this.peer.on("connection", (conn) => {
            conn.on("data", (data) => {
              this._handleIncomingOnHost(data, (reply) => {
                try {
                  conn.send(reply);
                } catch (e) {}
              }, conn);
            });
            conn.on("close", () => {
              const uid = conn._aqUid;
              if (uid) {
                this.guestConns.delete(uid);
                if (this.callbacks.onPeerLeave) this.callbacks.onPeerLeave(uid);
              }
            });
          });

          this.peer.on("error", (err) => {
            if (err && err.type === "unavailable-id") {
              this._emitError("이미 사용 중인 방 코드입니다. 다른 방 코드를 입력하거나 기존 방에 입장해 주세요.");
            } else {
              // 오프라인이거나 PeerJS 서버 지연 시에도 BroadcastChannel / Firebase로 작동
              this._emitStatus("local", "로컬 멀티탭 채널로 방 개설됨 (온라인 브로커 대기중)");
            }
          });
        } catch (e) {
          this._emitStatus("local", "로컬 멀티탭 모드로 동작 중");
        }
      } else {
        this._emitStatus("local", "로컬 멀티탭 모드로 동작 중");
      }

      this.connected = true;
      if (this.callbacks.onHostReady) {
        this.callbacks.onHostReady({
          roomCode: this.roomCode,
          hasPassword: this.hasPassword,
          hostId: this.myId,
          nick: this.myNick,
        });
      }
    }

    /**
     * 게스트로서 기존 방에 입장을 요청한다.
     */
    joinRoom({ roomCode, nick, password }) {
      this.disconnect();
      this.isHost = false;
      this.roomCode = String(roomCode).toUpperCase().trim();
      this.myNick = nick.trim();
      this.passwordHash = global.QuizEngine.hashRoomPassword(password, this.roomCode);

      let authResolved = false;

      const sendJoinReq = (sendFn) => {
        sendFn({
          type: "JOIN_REQ",
          uid: this.myId,
          nick: this.myNick,
          passwordHash: this.passwordHash,
          ts: Date.now(),
        });
      };

      // 1. BroadcastChannel 로 즉시 탐색 (같은 PC의 다른 탭에 호스트가 있는 경우 5ms 내 연결)
      this._initBroadcastChannel((msg) => {
        if (msg.targetUid && msg.targetUid !== this.myId) return;
        if (msg.type === "AUTH_OK" || msg.type === "AUTH_FAIL") {
          authResolved = true;
        }
        this._handleIncomingOnGuest(msg);
      });
      sendJoinReq((payload) => this._sendViaBroadcastChannel(payload));

      // 2. 선택적 Firebase 경유 입장
      if (this.fbUrl) {
        this._fbPost(`/rooms/${this.roomCode}/inbox.json`, {
          type: "JOIN_REQ",
          uid: this.myId,
          nick: this.myNick,
          passwordHash: this.passwordHash,
          ts: Date.now(),
        });
        this._startFirebasePolling();
      }

      // 3. PeerJS (WebRTC)로 원격 호스트에 연결
      if (typeof global.Peer !== "undefined") {
        try {
          this.peer = new global.Peer({
            debug: 1,
            config: {
              iceServers: [
                { urls: "stun:stun.l.google.com:19302" },
                { urls: "stun:stun1.l.google.com:19302" },
              ],
            },
          });

          this.peer.on("open", () => {
            if (authResolved) return;
            const targetPeerId = PEER_PREFIX + this.roomCode;
            const conn = this.peer.connect(targetPeerId, { reliable: true });
            this.hostConn = conn;

            conn.on("open", () => {
              this._emitStatus("online", "방 호스트와 연결됨 · 인증 확인 중...");
              sendJoinReq((payload) => conn.send(payload));
            });

            conn.on("data", (data) => {
              if (data.type === "AUTH_OK" || data.type === "AUTH_FAIL") {
                authResolved = true;
              }
              this._handleIncomingOnGuest(data);
            });

            conn.on("close", () => {
              if (!this.bc) {
                this._emitError("방장과의 연결이 종료되었습니다.");
              }
            });

            conn.on("error", () => {});
          });

          this.peer.on("error", () => {
            if (!authResolved) {
              this._emitError("방을 찾을 수 없거나 연결할 수 없습니다. 방 코드를 다시 확인해 주세요.");
            }
          });
        } catch (e) {}
      }

      // 6초 내 응답이 없으면 타임아웃 안내
      this.joinTimeout = setTimeout(() => {
        if (!authResolved) {
          this._emitError("해당 방 코드(" + this.roomCode + ")의 호스트가 응답하지 않습니다. 방 코드가 맞는지 확인해 주세요.");
        }
      }, 6500);
    }

    _initBroadcastChannel(guestHandler) {
      if (typeof BroadcastChannel === "undefined") return;
      try {
        this.bc = new BroadcastChannel(BC_PREFIX + this.roomCode);
        this.bc.onmessage = (ev) => {
          const data = ev.data;
          if (!data || data.senderId === this.myId) return;
          if (this.isHost) {
            this._handleIncomingOnHost(data, (reply) => {
              this._sendViaBroadcastChannel({ ...reply, targetUid: data.uid });
            });
          } else if (guestHandler) {
            guestHandler(data);
          }
        };
      } catch (e) {}
    }

    _sendViaBroadcastChannel(payload) {
      if (!this.bc) return;
      try {
        this.bc.postMessage({ ...payload, senderId: this.myId });
      } catch (e) {}
    }

    _handleIncomingOnHost(data, replyFn, peerConn = null) {
      if (!data || !data.type) return;

      if (data.type === "JOIN_REQ") {
        // 비밀번호 검증
        if (this.hasPassword && data.passwordHash !== this.passwordHash) {
          replyFn({
            type: "AUTH_FAIL",
            uid: data.uid,
            needPassword: true,
            reason: data.passwordHash
              ? "방 비밀번호가 일치하지 않습니다."
              : "비밀번호가 설정된 비공개 방입니다. 비밀번호를 입력해 주세요.",
          });
          return;
        }

        if (peerConn) {
          peerConn._aqUid = data.uid;
          this.guestConns.set(data.uid, peerConn);
        }

        if (this.callbacks.onJoinRequest) {
          const result = this.callbacks.onJoinRequest({
            uid: data.uid,
            nick: data.nick,
          });
          if (result && result.ok === false) {
            replyFn({
              type: "AUTH_FAIL",
              uid: data.uid,
              needPassword: false,
              reason: result.reason || "입장할 수 없습니다.",
            });
            return;
          }
          replyFn({
            type: "AUTH_OK",
            uid: data.uid,
            roomCode: this.roomCode,
            hasPassword: this.hasPassword,
            state: result ? result.state : null,
          });
        }
        return;
      }

      if (this.callbacks.onHostMessage) {
        this.callbacks.onHostMessage(data);
      }
    }

    _handleIncomingOnGuest(data) {
      if (!data || !data.type) return;
      if (data.targetUid && data.targetUid !== this.myId) return;

      if (data.type === "AUTH_FAIL") {
        if (this.joinTimeout) clearTimeout(this.joinTimeout);
        if (this.callbacks.onAuthFail) {
          this.callbacks.onAuthFail(data);
        }
        return;
      }

      if (data.type === "AUTH_OK") {
        if (this.joinTimeout) clearTimeout(this.joinTimeout);
        this.connected = true;
        this._emitStatus("online", "방 입장 완료");
        if (this.callbacks.onAuthOk) {
          this.callbacks.onAuthOk(data);
        }
        return;
      }

      if (this.callbacks.onGuestMessage) {
        this.callbacks.onGuestMessage(data);
      }
    }

    /**
     * 호스트가 모든 참가자에게 상태 또는 이벤트를 브로드캐스트한다.
     */
    broadcastFromHost(payload) {
      if (!this.isHost) return;
      this._sendViaBroadcastChannel(payload);
      for (const [, conn] of this.guestConns.entries()) {
        try {
          if (conn.open) conn.send(payload);
        } catch (e) {}
      }
      if (this.fbUrl && payload.type === "STATE_SYNC") {
        this._fbPut(`/rooms/${this.roomCode}/state.json`, {
          ...payload,
          updatedAt: Date.now(),
        });
      }
    }

    /**
     * 게스트(또는 호스트 자신)가 호스트에게 액션(레디, 채팅/정답 제출 등)을 전송한다.
     */
    sendToHost(payload) {
      const msg = { ...payload, uid: this.myId, nick: this.myNick, ts: Date.now() };
      if (this.isHost) {
        if (this.callbacks.onHostMessage) {
          this.callbacks.onHostMessage(msg);
        }
        return;
      }
      this._sendViaBroadcastChannel(msg);
      if (this.hostConn && this.hostConn.open) {
        try {
          this.hostConn.send(msg);
        } catch (e) {}
      }
      if (this.fbUrl) {
        this._fbPost(`/rooms/${this.roomCode}/inbox.json`, msg);
      }
    }

    async _fbPut(path, body) {
      if (!this.fbUrl) return;
      try {
        await fetch(this.fbUrl + path, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      } catch (e) {}
    }

    async _fbPost(path, body) {
      if (!this.fbUrl) return;
      try {
        await fetch(this.fbUrl + path, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      } catch (e) {}
    }

    _startFirebasePolling() {
      if (!this.fbUrl) return;
      if (this.fbPollTimer) clearInterval(this.fbPollTimer);
      let lastSeenTs = Date.now() - 2000;

      this.fbPollTimer = setInterval(async () => {
        if (!this.roomCode || !this.fbUrl) return;
        try {
          if (this.isHost) {
            const res = await fetch(`${this.fbUrl}/rooms/${this.roomCode}/inbox.json`);
            if (!res.ok) return;
            const inbox = await res.json();
            if (!inbox) return;
            for (const key of Object.keys(inbox)) {
              const item = inbox[key];
              if (item && item.ts > lastSeenTs) {
                lastSeenTs = item.ts;
                this._handleIncomingOnHost(item, (reply) => {
                  this._fbPut(`/rooms/${this.roomCode}/Direct_${item.uid}.json`, reply);
                });
              }
            }
          } else {
            const authRes = await fetch(`${this.fbUrl}/rooms/${this.roomCode}/Direct_${this.myId}.json`);
            if (authRes.ok) {
              const directMsg = await authRes.json();
              if (directMsg && !this.connected) {
                this._handleIncomingOnGuest(directMsg);
              }
            }
            const stateRes = await fetch(`${this.fbUrl}/rooms/${this.roomCode}/state.json`);
            if (stateRes.ok) {
              const st = await stateRes.json();
              if (st && st.updatedAt && st.updatedAt > lastSeenTs) {
                lastSeenTs = st.updatedAt;
                this._handleIncomingOnGuest(st);
              }
            }
          }
        } catch (e) {}
      }, 900);
    }

    _emitStatus(mode, text) {
      if (this.callbacks.onStatus) this.callbacks.onStatus({ mode, text });
    }

    _emitError(message) {
      if (this.callbacks.onError) this.callbacks.onError(message);
    }

    disconnect() {
      if (this.joinTimeout) {
        clearTimeout(this.joinTimeout);
        this.joinTimeout = null;
      }
      if (this.fbPollTimer) {
        clearInterval(this.fbPollTimer);
        this.fbPollTimer = null;
      }
      if (this.bc) {
        try {
          this.bc.close();
        } catch (e) {}
        this.bc = null;
      }
      if (this.hostConn) {
        try {
          this.hostConn.close();
        } catch (e) {}
        this.hostConn = null;
      }
      for (const [, conn] of this.guestConns.entries()) {
        try {
          conn.close();
        } catch (e) {}
      }
      this.guestConns.clear();
      if (this.peer) {
        try {
          this.peer.destroy();
        } catch (e) {}
        this.peer = null;
      }
      this.connected = false;
    }
  }

  global.RoomNetwork = RoomNetwork;
})(typeof window !== "undefined" ? window : globalThis);
