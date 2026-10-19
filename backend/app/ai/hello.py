"""The first Bedrock call, from a laptop: ``make llm-hello``.

Prints the answer, why it stopped, and the tokens it cost - the three things to
read in every response, not only the text.
"""

from anthropic import AnthropicBedrockMantle

from app.config import get_settings


def main() -> None:
    settings = get_settings()
    client = AnthropicBedrockMantle(aws_region=settings.bedrock_region)
    msg = client.messages.create(
        model=settings.parser_model,
        max_tokens=1024,
        output_config={"effort": "low"},  # short, cheap answers
        messages=[{"role": "user", "content": "In one sentence: what is an ISO week?"}],
    )
    print(next(b.text for b in msg.content if b.type == "text"))
    print(
        f"model={settings.parser_model} stop_reason={msg.stop_reason} "
        f"input_tokens={msg.usage.input_tokens} output_tokens={msg.usage.output_tokens}"
    )


if __name__ == "__main__":
    main()
