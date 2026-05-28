#!/usr/bin/env python3
import asyncio
import os
import sys

# Add the current directory to sys.path so we can import from 'api' and 'pipeline'
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from api.ai_service import AIService, ModelConfig, _cache

async def test_layer(name, config):
    ai = AIService()
    # Clear in-memory cache to force a fresh call to the provider
    _cache.clear()
    try:
        # We classify a simple message
        intent, layer = await ai.classify_intent("من غاب اليوم", config=config)
        # Avoid non-ASCII characters to prevent Windows console encoding crashes
        print(f"[SUCCESS] {name:15} | Intent: {intent:18} | Layer Used: {layer}")
        return True, f"Success (Intent: {intent}, Layer: {layer})"
    except Exception as e:
        print(f"[FAILED]  {name:15} | Error: {e}")
        return False, str(e)

async def main():
    print("=" * 70)
    print("ARAK CHATBOT - MULTI-LAYER FALLBACK ORCHESTRATOR DIAGNOSTIC")
    print("=" * 70)
    print("Testing each individual layer in isolation to verify API keys and local fallbacks...\n")

    results = {}

    # 1. Test Groq Layer
    cfg_groq = ModelConfig(
        enable_groq=True,
        enable_gemini_lite=False,
        enable_gemini_flash=False,
        enable_ollama=False,
        enable_sklearn=False
    )
    results["Groq (Llama-3.3)"] = await test_layer("Groq", cfg_groq)

    # 2. Test Gemini 2.0 Flash Lite Layer
    cfg_lite = ModelConfig(
        enable_groq=False,
        enable_gemini_lite=True,
        enable_gemini_flash=False,
        enable_ollama=False,
        enable_sklearn=False
    )
    results["Gemini 2.0 Lite"] = await test_layer("Gemini 2.0 Lite", cfg_lite)

    # 3. Test Gemini 1.5 Flash Layer
    cfg_flash = ModelConfig(
        enable_groq=False,
        enable_gemini_lite=False,
        enable_gemini_flash=True,
        enable_ollama=False,
        enable_sklearn=False
    )
    results["Gemini 1.5 Flash"] = await test_layer("Gemini 1.5 Flash", cfg_flash)

    # 4. Test sklearn fallback Layer
    cfg_sklearn = ModelConfig(
        enable_groq=False,
        enable_gemini_lite=False,
        enable_gemini_flash=False,
        enable_ollama=False,
        enable_sklearn=True
    )
    results["sklearn classifier"] = await test_layer("sklearn Fallback", cfg_sklearn)

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY OF DIAGNOSTIC REPORT")
    print("=" * 70)
    for layer, (success, msg) in results.items():
        status = "OK" if success else "FAILED"
        print(f"- {layer:20} : {status:10} | {msg}")
    print("=" * 70)

if __name__ == "__main__":
    # If there is an active event loop in this thread, run with that, otherwise create one
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            asyncio.run(main())
        else:
            asyncio.run(main())
    except RuntimeError:
        asyncio.run(main())
