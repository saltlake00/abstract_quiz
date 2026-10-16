// -*- coding: utf-8 -*-
/**
 * engine.js
 * 추상화 그림맞추기 온라인 핵심 규칙 엔진
 * - 정답 정규화 및 편집거리(오타 허용) 판정
 * - 시간에 따른 도형 공개 개수(비선형 거듭제곱 곡선) 계산
 * - 도형 개수 및 선착순 순위에 따른 점수 산정
 * - 방 비밀번호 해시 생성 및 검증
 */

(function (global) {
  "use strict";

  /**
   * 입력 문자열을 소문자화하고 영문·숫자·완성형 한글만 남긴다.
   */
  function normalizeText(raw) {
    if (!raw || typeof raw !== "string") return "";
    return raw.toLowerCase().replace(/[^0-9a-z가-힣]/g, "");
  }

  /**
   * 두 문자열 사이의 레벤슈타인 편집 거리를 계산한다.
   */
  function levenshtein(a, b) {
    if (a === b) return 0;
    const m = a.length;
    const n = b.length;
    if (m === 0) return n;
    if (n === 0) return m;
    const dp = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
    for (let i = 0; i <= m; i++) dp[i][0] = i;
    for (let j = 0; j <= n; j++) dp[0][j] = j;
    for (let i = 1; i <= m; i++) {
      for (let j = 1; j <= n; j++) {
        const cost = a[i - 1] === b[j - 1] ? 0 : 1;
        dp[i][j] = Math.min(
          dp[i - 1][j] + 1,
          dp[i][j - 1] + 1,
          dp[i - 1][j - 1] + cost
        );
      }
    }
    return dp[m][n];
  }

  /**
   * 사용자 입력이 문제의 정답 목록과 일치하는지 판정한다.
   * 5글자 이상인 정답에 대해서는 allowTypo가 켜져 있을 때 편집거리 1 오타를 허용한다.
   */
  function checkAnswer(userInput, acceptedAnswers, allowTypo = true) {
    const normInput = normalizeText(userInput);
    if (!normInput || !Array.isArray(acceptedAnswers)) return false;

    for (const ans of acceptedAnswers) {
      const normAns = normalizeText(ans);
      if (!normAns) continue;
      if (normInput === normAns) return true;
      if (allowTypo && normAns.length >= 5 && normInput.length >= 4) {
        if (levenshtein(normInput, normAns) <= 1) return true;
      }
    }
    return false;
  }

  /**
   * 경과 시간(ms)과 총 제한 시간(ms), 전체 도형 수(totalPolygons)를 받아
   * 현재 화면에 표시할 도형 개수 k를 반환한다.
   * 초반에는 느리게(추상화 단계), 후반에는 빠르게(세부 묘사 단계) 공개된다.
   */
  function computeVisibleCount(elapsedMs, durationMs, totalPolygons, gamma = 1.85) {
    if (totalPolygons <= 0) return 0;
    if (elapsedMs <= 0) return 1;
    if (elapsedMs >= durationMs) return totalPolygons;
    const ratio = Math.min(1, Math.max(0, elapsedMs / durationMs));
    const k = Math.floor(totalPolygons * Math.pow(ratio, gamma));
    return Math.min(totalPolygons, Math.max(1, k));
  }

  /**
   * 정답을 맞힌 시점의 도형 개수(k), 전체 도형 수(totalPolygons),
   * 해당 라운드의 몇 번째 정답자인지(rankIndex: 0=1등, 1=2등, 2=3등...)를 받아 점수를 계산한다.
   */
  function calculateScore(k, totalPolygons, rankIndex = 0) {
    const ratio = totalPolygons > 0 ? Math.min(1, Math.max(0, k / totalPolygons)) : 1;
    const baseScore = Math.max(20, Math.round(100 * (1 - 0.8 * ratio)));
    const rankBonuses = [30, 15, 5];
    const bonus = rankIndex >= 0 && rankIndex < rankBonuses.length ? rankBonuses[rankIndex] : 0;
    return {
      base: baseScore,
      bonus: bonus,
      total: baseScore + bonus,
    };
  }

  /**
   * 방 비밀번호를 해시 문자열로 변환한다 (평문 노출 방지).
   * 빈 문자열이면 빈 해시를 반환하여 공개방임을 나타낸다.
   */
  function hashRoomPassword(password, roomCode = "") {
    const clean = (password || "").trim();
    if (!clean) return "";
    const salted = `aq_salt_${String(roomCode).toUpperCase()}_${clean}`;
    // FNV1a 64비트 결합 해시 (동기식 & 모든 브라우저/프로토콜 호환)
    let h1 = 0x811c9dc5;
    let h2 = 0xcbf29ce4;
    for (let i = 0; i < salted.length; i++) {
      const ch = salted.charCodeAt(i);
      h1 ^= ch;
      h1 = Math.imul(h1, 0x01000193) >>> 0;
      h2 ^= ch * 31;
      h2 = Math.imul(h2, 0x01000193) >>> 0;
    }
    return h1.toString(16).padStart(8, "0") + h2.toString(16).padStart(8, "0");
  }

  /**
   * 읽기 쉬운 6자리 영문·숫자 방 코드를 생성한다 (혼동하기 쉬운 O, 0, I, 1 제외).
   */
  function generateRoomCode(length = 5) {
    const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
    let out = "";
    for (let i = 0; i < length; i++) {
      out += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return out;
  }

  const QuizEngine = {
    normalizeText,
    levenshtein,
    checkAnswer,
    computeVisibleCount,
    calculateScore,
    hashRoomPassword,
    generateRoomCode,
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = QuizEngine;
  }
  global.QuizEngine = QuizEngine;
})(typeof window !== "undefined" ? window : globalThis);
