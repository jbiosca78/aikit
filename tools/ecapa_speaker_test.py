#!/usr/bin/env python3
"""Minimal ECAPA speaker identification test tool.

Usage examples:
  python tools/ecapa_speaker_test.py enroll --user ana --wav ana_01.wav --db speakers.json
  python tools/ecapa_speaker_test.py enroll --user ana --wav ana_02.wav --db speakers.json
  python tools/ecapa_speaker_test.py predict --wav test.wav --db speakers.json --threshold 0.62
  python tools/ecapa_speaker_test.py compare --wav-a ana_01.wav --wav-b ana_02.wav
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Dict, List

import torch
import torchaudio
from speechbrain.inference.speaker import EncoderClassifier

MODEL_SOURCE = "speechbrain/spkrec-ecapa-voxceleb"
MODEL_CACHE = "./.ecapa_cache"
TARGET_SR = 16000


class SpeakerDb:
    def __init__(self, path: Path):
        self.path = path
        self.data: Dict[str, Dict[str, List[List[float]]]] = {"users": {}}
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
            self.data.setdefault("users", {})

    def save(self) -> None:
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")

    def add_embedding(self, user: str, emb: List[float]) -> None:
        users = self.data["users"]
        users.setdefault(user, {"samples": []})
        users[user].setdefault("samples", [])
        users[user]["samples"].append(emb)

    def centroids(self) -> Dict[str, List[float]]:
        out: Dict[str, List[float]] = {}
        for user, payload in self.data.get("users", {}).items():
            samples = payload.get("samples", [])
            if not samples:
                continue
            dim = len(samples[0])
            sums = [0.0] * dim
            for sample in samples:
                for i, v in enumerate(sample):
                    sums[i] += v
            out[user] = [v / len(samples) for v in sums]
        return out


def l2_normalize(vec: List[float]) -> List[float]:
    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        return vec
    return [v / norm for v in vec]


def cosine(a: List[float], b: List[float]) -> float:
    if len(a) != len(b):
        return -1.0
    an = l2_normalize(a)
    bn = l2_normalize(b)
    return sum(x * y for x, y in zip(an, bn))


def load_waveform(path: Path) -> torch.Tensor:
    wav, sr = torchaudio.load(str(path))
    if wav.dim() == 2 and wav.size(0) > 1:
        wav = wav.mean(dim=0, keepdim=True)
    if sr != TARGET_SR:
        wav = torchaudio.functional.resample(wav, orig_freq=sr, new_freq=TARGET_SR)
    return wav


def embedding_for_wav(classifier: EncoderClassifier, wav_path: Path) -> List[float]:
    if not wav_path.exists():
        raise FileNotFoundError(f"WAV not found: {wav_path}")
    wav = load_waveform(wav_path)
    with torch.no_grad():
        emb = classifier.encode_batch(wav)
    flat = emb.squeeze().cpu().tolist()
    if not isinstance(flat, list):
        raise RuntimeError("Unexpected embedding output format")
    return l2_normalize([float(x) for x in flat])


def cmd_enroll(args: argparse.Namespace, classifier: EncoderClassifier) -> None:
    db = SpeakerDb(Path(args.db))
    emb = embedding_for_wav(classifier, Path(args.wav))
    db.add_embedding(args.user, emb)
    db.save()
    count = len(db.data["users"][args.user]["samples"])
    print(json.dumps({"ok": True, "user": args.user, "samples": count, "db": args.db}, indent=2))


def cmd_predict(args: argparse.Namespace, classifier: EncoderClassifier) -> None:
    db = SpeakerDb(Path(args.db))
    centroids = db.centroids()
    if not centroids:
        raise RuntimeError("No enrolled users in DB")

    emb = embedding_for_wav(classifier, Path(args.wav))
    scored = [{"user": user, "score": cosine(emb, centroid)} for user, centroid in centroids.items()]
    scored.sort(key=lambda x: x["score"], reverse=True)
    best = scored[0]
    decision = best["user"] if best["score"] >= args.threshold else "unknown"

    print(
        json.dumps(
            {
                "ok": True,
                "decision": decision,
                "threshold": args.threshold,
                "best": best,
                "ranking": scored,
            },
            indent=2,
        )
    )


def cmd_compare(args: argparse.Namespace, classifier: EncoderClassifier) -> None:
    emb_a = embedding_for_wav(classifier, Path(args.wav_a))
    emb_b = embedding_for_wav(classifier, Path(args.wav_b))
    print(json.dumps({"ok": True, "score": cosine(emb_a, emb_b)}, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="ECAPA speaker-ID test utility")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_enroll = sub.add_parser("enroll", help="Add a WAV sample for a user")
    p_enroll.add_argument("--user", required=True, help="User id/name")
    p_enroll.add_argument("--wav", required=True, help="Path to WAV file")
    p_enroll.add_argument("--db", default="speakers.json", help="Speaker DB JSON path")

    p_predict = sub.add_parser("predict", help="Identify speaker from WAV")
    p_predict.add_argument("--wav", required=True, help="Path to WAV file")
    p_predict.add_argument("--db", default="speakers.json", help="Speaker DB JSON path")
    p_predict.add_argument("--threshold", type=float, default=0.62, help="Known-vs-unknown threshold")

    p_compare = sub.add_parser("compare", help="Compare similarity between two WAVs")
    p_compare.add_argument("--wav-a", required=True, help="First WAV path")
    p_compare.add_argument("--wav-b", required=True, help="Second WAV path")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    classifier = EncoderClassifier.from_hparams(source=MODEL_SOURCE, savedir=MODEL_CACHE)

    if args.cmd == "enroll":
        cmd_enroll(args, classifier)
    elif args.cmd == "predict":
        cmd_predict(args, classifier)
    elif args.cmd == "compare":
        cmd_compare(args, classifier)
    else:
        raise ValueError(f"Unsupported command: {args.cmd}")


if __name__ == "__main__":
    main()
