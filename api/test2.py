import edge_tts
import asyncio
import time
import os

async def benchmark_edge_tts(text, output_path, num_runs=10):
    """
    Benchmarks Edge TTS generation time for a given text.

    Args:
        text (str): The text to convert to speech.
        output_path (str): Path to save the generated audio file (for testing, can be discarded).
        num_runs (int): Number of times to run the benchmark and average the result.
    """

    generation_times = []

    for i in range(num_runs):
        start_time = time.time()
        try:
            tts = edge_tts.Communicate(text, voice="zh-CN-XiaoyiNeural") # Or your preferred voice
            await tts.save(output_path) # We include save time in the benchmark for a complete TTS cycle
            end_time = time.time()
            generation_time = end_time - start_time
            generation_times.append(generation_time)
            print(f"Run {i+1}/{num_runs}: Edge TTS Generation Time: {generation_time:.4f} seconds")

        except Exception as e:
            print(f"Run {i+1}/{num_runs}: Edge TTS Generation Failed: {str(e)}")
            generation_times.append(None) # Record None for failed runs

    # Clean up the test audio file (optional)
    if os.path.exists(output_path):
        os.remove(output_path)

    valid_times = [t for t in generation_times if t is not None] # Filter out failed runs

    if valid_times:
        average_time = sum(valid_times) / len(valid_times)
        print(f"\n--- Edge TTS Benchmark Summary ---")
        print(f"Average Generation Time (over {len(valid_times)} successful runs): {average_time:.4f} seconds")
    else:
        print("\n--- Edge TTS Benchmark Summary ---")
        print("No successful TTS generations to calculate average time.")


async def main():
    test_sentence = "你好，这是一段20个字的测试文本，用来测试Edge TTS的语音生成速度。" # Example 20-word sentence in Chinese
    output_file = "edge_tts_benchmark_test.wav"
    num_benchmark_runs = 10 # You can adjust the number of benchmark runs

    print(f"Benchmarking Edge TTS for sentence: \"{test_sentence}\" ({num_benchmark_runs} runs)")
    await benchmark_edge_tts(test_sentence, output_file, num_benchmark_runs)


if __name__ == "__main__":
    asyncio.run(main())



