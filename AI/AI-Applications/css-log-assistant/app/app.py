import json

import streamlit as st

from config import load_config
from es_mcp_client import EsClient, EsClientConfig
from maas_client import MaaSClient, MaaSConfig

QUERY_SYSTEM = (
    "You are a log search assistant. Convert the user question into a single Elasticsearch Query DSL request. "
    "Return ONLY a JSON object with keys: index, body. "
    "index must be an index pattern. body must be valid for Elasticsearch _search.\n\n"
    "Index schema (use these exact field names):\n"
    "- timestamp (type: date) — NOT @timestamp, use \"timestamp\" only\n"
    "- order_id, country, country_code, city (type: keyword)\n"
    "- restaurant_id, restaurant_name (keyword/text)\n"
    "- customer_id, driver_id (keyword)\n"
    "- order_status (keyword): delivered, preparing, in_transit, cancelled_by_customer, cancelled_by_restaurant, payment_failed, delivery_timeout, pending\n"
    "- total_amount (double), currency (keyword)\n"
    "- items_count, delivery_time_minutes (integer)\n"
    "- distance_km (double)\n"
    "- payment_method, platform (keyword)\n"
    "- error_code (keyword), error_message (text)\n\n"
    "Important: Always use \"timestamp\" for time fields, never \"@timestamp\"."
)

SUMMARY_SYSTEM = (
    "You are a log analytics assistant. Answer the user's question using the Elasticsearch search results. "
    "Be concise and respond in English."
)


def _get_clients():
    cfg = load_config()

    if "es_client" not in st.session_state:
        st.session_state.es_client = EsClient(
            EsClientConfig(
                es_url=cfg.es_url,
                username=cfg.es_username,
                password=cfg.es_password,
                insecure=cfg.es_insecure,
            )
        )

    if "maas_client" not in st.session_state:
        st.session_state.maas_client = MaaSClient(
            MaaSConfig(
                api_key=cfg.maas_api_key,
                base_url=cfg.maas_base_url,
                model=cfg.maas_model,
            )
        )

    return cfg, st.session_state.es_client, st.session_state.maas_client


def _extract_hits(results, limit=5):
    hits = results.get("hits", {}).get("hits", [])
    out = []
    for h in hits[:limit]:
        src = h.get("_source", {})
        out.append(
            {
                "timestamp": src.get("timestamp"),
                "country": src.get("country"),
                "city": src.get("city"),
                "order_status": src.get("order_status"),
                "total_amount": src.get("total_amount"),
                "currency": src.get("currency"),
                "error_code": src.get("error_code"),
                "error_message": src.get("error_message"),
            }
        )
    return out


def _stream_and_collect(maas, messages, system, temperature, thinking_placeholder, text_placeholder):
    """Stream from MAAS, update placeholders in real-time, return (text, thinking)."""
    thinking_buf = []
    text_buf = []
    for chunk in maas.messages_stream(
        messages=messages, system=system, temperature=temperature,
    ):
        if chunk["type"] == "thinking_delta":
            thinking_buf.append(chunk["text"])
            thinking_placeholder.markdown("".join(thinking_buf))
        elif chunk["type"] == "text_delta":
            text_buf.append(chunk["text"])
            text_placeholder.markdown("".join(text_buf))
    return "".join(text_buf), "".join(thinking_buf)


def main():
    st.set_page_config(page_title="CSS Log Query Assistant", layout="wide")
    st.title("CSS Log Query Assistant")

    cfg, es, maas = _get_clients()

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            if msg.get("thinking"):
                with st.expander("Thinking"):
                    st.markdown(msg["thinking"])
            st.markdown(msg["content"])
            if "dsl" in msg:
                with st.expander("Elasticsearch Query DSL"):
                    st.code(json.dumps(msg["dsl"], ensure_ascii=False, indent=2), language="json")
            if "sample_hits" in msg:
                with st.expander("Sample hits"):
                    st.json(msg["sample_hits"])

    question = st.chat_input("Ask a question about food delivery logs")
    if not question:
        return

    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        try:
            # Phase 1: Stream query generation
            st.markdown("**Generating Elasticsearch query...**")
            thinking_ph = st.empty()
            text_ph = st.empty()
            with st.expander("Thinking", expanded=True):
                query_thinking_ph = st.empty()
            query_text_ph = st.empty()

            query_text, query_thinking = _stream_and_collect(
                maas,
                messages=[{"role": "user", "content": f"index_pattern: {cfg.index_pattern}\nquestion: {question}"}],
                system=QUERY_SYSTEM,
                temperature=0.0,
                thinking_placeholder=query_thinking_ph,
                text_placeholder=query_text_ph,
            )

            # Parse the generated query
            content = query_text.strip()
            if content.startswith("```"):
                content = content.strip("`")
                content = content.replace("json", "", 1).strip()
            dsl_req = json.loads(content)
            index = dsl_req["index"]
            body = dsl_req["body"]

            # Phase 2: Execute ES query
            st.markdown("**Executing query...**")
            results = es.search(index=index, body=body)
            sample_hits = _extract_hits(results)

            # Phase 3: Stream result analysis
            st.markdown("**Analyzing results...**")
            with st.expander("Thinking", expanded=True):
                answer_thinking_ph = st.empty()
            answer_text_ph = st.empty()

            answer_text, answer_thinking = _stream_and_collect(
                maas,
                messages=[{
                    "role": "user",
                    "content": json.dumps(
                        {"question": question, "results": {"hits": results.get("hits"), "aggregations": results.get("aggregations")}},
                        ensure_ascii=False,
                    ),
                }],
                system=SUMMARY_SYSTEM,
                temperature=0.2,
                thinking_placeholder=answer_thinking_ph,
                text_placeholder=answer_text_ph,
            )

            thinking = ""
            if query_thinking:
                thinking += "**Query generation:**\n" + query_thinking
            if answer_thinking:
                if thinking:
                    thinking += "\n\n"
                thinking += "**Result analysis:**\n" + answer_thinking

        except Exception as e:
            answer_text = f"Error: {e}"
            dsl_req = None
            sample_hits = None
            thinking = None

        # Final render: clear streaming artifacts and show final state
        st.empty()  # spacer
        if thinking:
            with st.expander("Thinking"):
                st.markdown(thinking)
        st.markdown(answer_text)
        if dsl_req is not None:
            with st.expander("Elasticsearch Query DSL"):
                st.code(json.dumps(dsl_req, ensure_ascii=False, indent=2), language="json")
        if sample_hits is not None:
            with st.expander("Sample hits"):
                st.json(sample_hits)

    assistant_msg = {"role": "assistant", "content": answer_text}
    if thinking:
        assistant_msg["thinking"] = thinking
    if dsl_req is not None:
        assistant_msg["dsl"] = dsl_req
    if sample_hits is not None:
        assistant_msg["sample_hits"] = sample_hits
    st.session_state.messages.append(assistant_msg)


if __name__ == "__main__":
    main()
