from src.integrations.ai.providers.google import GoogleProvider


def test_google_generation_config_maps_openai_style_options():
    result = GoogleProvider._generation_config({"max_tokens": 4, "temperature": 0, "top_p": 0.9, "top_k": 10})
    assert result == {"temperature": 0, "maxOutputTokens": 4, "topP": 0.9, "topK": 10}


def test_google_contents_ignores_system_messages_and_maps_roles():
    result = GoogleProvider._contents([
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi"},
    ])
    assert result == [
        {"role": "user", "parts": [{"text": "Hello"}]},
        {"role": "model", "parts": [{"text": "Hi"}]},
    ]
