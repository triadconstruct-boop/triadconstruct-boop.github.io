#!/usr/bin/env python3
"""Compatibility refiner: v3 performs scoring inside the lifecycle pipeline."""

from yy_engine.pipeline import main


if __name__ == "__main__":
    raise SystemExit(main(["--offline"]))
