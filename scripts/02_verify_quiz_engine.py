# -*- coding: utf-8 -*-
"""
02_verify_quiz_engine.py
웹 애플리케이션 JS 모듈 문법 검사 및 핵심 규칙 엔진(engine.js),
15문항 데이터셋(questions.js) 무결성 검증 스크립트.
결과를 intermediate_results/engine_verification_results.csv (utf-8-sig)로 저장합니다.
"""

import os
import csv
import json
import subprocess

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INTERMEDIATE_DIR = os.path.join(BASE_DIR, "intermediate_results")


def run_node_verification():
    node_script = r"""
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const base = process.cwd();
const Engine = require(path.join(base, 'js', 'engine.js'));

const qCode = fs.readFileSync(path.join(base, 'data', 'questions.js'), 'utf8');
const sandbox = { window: {} };
vm.createContext(sandbox);
vm.runInContext(qCode, sandbox);
const questions = sandbox.window.QUIZ_QUESTIONS || [];

const results = [];
function assertTest(name, cond, detail) {
  results.push({ test_name: name, passed: Boolean(cond), detail: String(detail) });
}

// 1. 데이터셋 15문항 검증
assertTest('dataset_count_15', questions.length === 15, `count=${questions.length}`);
const allHave260 = questions.every(q => Array.isArray(q.polygons) && q.polygons.length === 260);
assertTest('dataset_polygons_260', allHave260, 'All 15 items have 260 polygons');

// 2. 정규화 및 정답 판정 검증
assertTest('norm_korean_punct', Engine.normalizeText('모나 리자!@#') === '모나리자', Engine.normalizeText('모나 리자!@#'));
assertTest('answer_exact_match', Engine.checkAnswer('모나 리자!', ['모나리자', '다빈치']) === true, 'Exact normalized match');
assertTest('answer_typo_match_long', Engine.checkAnswer('진주귀걸이를한소냐', ['진주귀걸이를한소녀'], true) === true, '1-char typo allowed on length>=5');
assertTest('answer_wrong_reject', Engine.checkAnswer('피카소', ['모나리자', '다빈치'], true) === false, 'Wrong answer rejected');

// 3. 도형 단계 공개 수식 단조증가 검증
const k0 = Engine.computeVisibleCount(0, 30000, 260);
const k10 = Engine.computeVisibleCount(10000, 30000, 260);
const k20 = Engine.computeVisibleCount(20000, 30000, 260);
const k30 = Engine.computeVisibleCount(30000, 30000, 260);
assertTest('visible_count_monotonic', k0 === 1 && k0 < k10 && k10 < k20 && k20 < k30 && k30 === 260, `k=[${k0}, ${k10}, ${k20}, ${k30}]`);

// 4. 점수 산정 검증 (빠를수록, 선착순일수록 고득점)
const sEarly1st = Engine.calculateScore(20, 260, 0);
const sLate1st = Engine.calculateScore(220, 260, 0);
const sEarly2nd = Engine.calculateScore(20, 260, 1);
assertTest('score_early_vs_late', sEarly1st.total > sLate1st.total, `early=${sEarly1st.total}, late=${sLate1st.total}`);
assertTest('score_rank_bonus', sEarly1st.total - sEarly2nd.total === 15, `1st=${sEarly1st.total}, 2nd=${sEarly2nd.total}`);

// 5. 방 비밀번호 해시 검증
const hOpen = Engine.hashRoomPassword('', 'AB123');
const hLock1 = Engine.hashRoomPassword('1234', 'AB123');
const hLock2 = Engine.hashRoomPassword('1234', 'AB123');
const hWrong = Engine.hashRoomPassword('9999', 'AB123');
assertTest('password_hash_open', hOpen === '', 'Empty password yields empty hash');
assertTest('password_hash_match', hLock1.length === 16 && hLock1 === hLock2 && hLock1 !== hWrong, `hash=${hLock1}`);

// 6. 랜덤 닉네임 생성 검증
const sampleNicks = Array.from({length: 5}, () => Engine.generateRandomNickname());
const validFormat = sampleNicks.every(n => typeof n === 'string' && n.includes(' ') && n.length >= 4 && n.length <= 16);
assertTest('random_nickname_format', validFormat, sampleNicks.join(' | '));

console.log(JSON.stringify(results));
"""
    js_files = ["data/questions.js", "js/engine.js", "js/net.js", "js/app.js"]
    rows = []

    for rel in js_files:
        full = os.path.join(BASE_DIR, rel)
        proc = subprocess.run(["node", "--check", full], capture_output=True, text=True)
        rows.append({
            "test_name": f"syntax_{rel}",
            "passed": proc.returncode == 0,
            "detail": "OK" if proc.returncode == 0 else proc.stderr.strip(),
        })

    proc = subprocess.run(["node", "-e", node_script], cwd=BASE_DIR, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"Node test failed: {proc.stderr}")

    unit_results = json.loads(proc.stdout.strip())
    rows.extend(unit_results)

    out_csv = os.path.join(INTERMEDIATE_DIR, "engine_verification_results.csv")
    with open(out_csv, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["test_name", "passed", "detail"])
        writer.writeheader()
        writer.writerows(rows)

    failed = [r for r in rows if not r["passed"]]
    print(f"Total tests: {len(rows)}, Passed: {len(rows) - len(failed)}, Failed: {len(failed)}")
    for r in rows:
        status = "PASS" if r["passed"] else "FAIL"
        print(f"  [{status}] {r['test_name']} -> {r['detail']}")
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    run_node_verification()
