"""The first Bedrock call, from a laptop: ``make llm-hello``.

Prints the answer, why it stopped, and the tokens it cost - the three things to
read in every response, not only the text. PARSER_API picks the API, as for
the parser: ``converse`` (bedrock-runtime) or ``messages`` (bedrock-mantle).
"""

from app.config import get_settings

QUESTION = "In one sentence: what is an ISO week?"


def main() -> None:
    settings = get_settings()
    if settings.parser_api == "messages":
        from anthropic import AnthropicBedrockMantle

        client = AnthropicBedrockMantle(aws_region=settings.bedrock_region)
        msg = client.messages.create(
            model=settings.parser_model,
            max_tokens=1024,
            output_config={"effort": "low"},  # short, cheap answers
            messages=[{"role": "user", "content": QUESTION}],
        )
        text = next(b.text for b in msg.content if b.type == "text")
        stop, tokens_in, tokens_out = (
            msg.stop_reason,
            msg.usage.input_tokens,
            msg.usage.output_tokens,
        )
    else:
        import boto3

        brt = boto3.client("bedrock-runtime", region_name=settings.bedrock_region)
        resp = brt.converse(
            modelId=settings.parser_model,
            messages=[{"role": "user", "content": [{"text": QUESTION}]}],
            inferenceConfig={"maxTokens": 200},
        )
        text = resp["output"]["message"]["content"][0]["text"]
        stop = resp["stopReason"]
        tokens_in, tokens_out = resp["usage"]["inputTokens"], resp["usage"]["outputTokens"]

    print(text)
    print(
        f"api={settings.parser_api} model={settings.parser_model} stop_reason={stop} "
        f"input_tokens={tokens_in} output_tokens={tokens_out}"
    )


if __name__ == "__main__":
    main()
