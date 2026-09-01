"""DP-357: build the exact extraction request bodies, inside the Hindsight container.

The bake-off must score the real prompt, not a reimplementation of it. Hindsight
assembles the system prompt from a base template, the bank's retain_mission, the
extraction-mode guidelines, an optional causal-links section and a dynamically
built entity-labels schema -- and constrains the response server-side with a
json_schema derived from a Pydantic model. Reproducing that by hand would score a
strawman, so this script imports the running server's own code.

Run it INSIDE the hindsight-memory container:

    docker cp fixtures.json  hindsight-memory:/tmp/fixtures.json
    docker cp build_bodies.py hindsight-memory:/tmp/build_bodies.py
    docker exec hindsight-memory python /tmp/build_bodies.py \
        --fixtures /tmp/fixtures.json --overrides /tmp/overrides.json --out /tmp/bodies.json
    docker cp hindsight-memory:/tmp/bodies.json bodies.json

The resolved config is rebuilt the same way ConfigResolver.resolve_full_config
does -- env-derived global config, then the bank's stored overrides on top -- so
no database connection is needed.

Output: one request body per fixture, complete except for "model", which the
runner fills in per candidate.
"""

import argparse
import json
from dataclasses import asdict


def build_config(overrides):
    from hindsight_api.config import HindsightConfig, _get_raw_config

    config_dict = asdict(_get_raw_config())
    unknown = [k for k in overrides if k not in config_dict]
    if unknown:
        raise SystemExit(f"bank overrides name fields the config does not have: {unknown}")
    config_dict.update(overrides)
    return HindsightConfig(**config_dict)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fixtures", required=True)
    ap.add_argument("--overrides", required=True, help="bank config overrides, from GET /config")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    from hindsight_api.engine.retain.fact_extraction import (
        _build_extraction_prompt_and_schema,
        _build_user_message,
    )

    with open(args.fixtures, encoding="utf-8") as fh:
        fixtures = json.load(fh)
    with open(args.overrides, encoding="utf-8") as fh:
        overrides = json.load(fh)

    config = build_config(overrides)
    prompt, response_schema = _build_extraction_prompt_and_schema(config)
    schema = response_schema.model_json_schema()

    # Mirrors _build_request_body: temperature 0.1, max_completion_tokens from
    # config, response_format named "facts". "model" is left for the runner.
    bodies = {}
    for fid, fx in fixtures.items():
        user_message = _build_user_message(
            fx["text"],
            fx["chunk_index"],
            fx["total_chunks"],
            fx.get("event_date"),
            "",  # production retain sends no context; census shows context empty on 100% of facts
            fx.get("metadata") or None,
            None,  # no agent_name in the ingester's retain_params
        )
        body = {
            "messages": [
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.1,
            "response_format": {"type": "json_schema", "json_schema": {"name": "facts", "schema": schema}},
        }
        if config.retain_max_completion_tokens:
            body["max_completion_tokens"] = config.retain_max_completion_tokens
        bodies[fid] = body

    meta = {
        "extraction_mode": config.retain_extraction_mode,
        "extract_causal_links": config.retain_extract_causal_links,
        "max_completion_tokens": config.retain_max_completion_tokens,
        "llm_output_language": config.llm_output_language,
        "response_schema_class": response_schema.__name__,
        "system_prompt_chars": len(prompt),
        "schema_chars": len(json.dumps(schema)),
        "retain_mission_present": bool(config.retain_mission),
    }

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"meta": meta, "bodies": bodies}, fh, ensure_ascii=False)

    print(json.dumps(meta, indent=1))
    for fid, body in bodies.items():
        print(f"{fid:22} user_message={len(body['messages'][1]['content']):6} chars")


if __name__ == "__main__":
    main()
