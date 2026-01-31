"""验证 P95/P99 延迟优化效果"""

import asyncio
import statistics
import time
import httpx

async def benchmark_latency():
    """Benchmark P50/P95/P99 latencies."""
    latencies = []
    
    async with httpx.AsyncClient() as client:
        for i in range(1000):
            start = time.time()
            try:
                response = await client.post(
                    "http://localhost:8000/v1/chat/completions",
                    headers={"Authorization": "Bearer sk-stress-test-001"},
                    json={
                        "model": "deepseek-chat",
                        "messages": [{"role": "user", "content": "Hello"}],
                        "stream": False
                    },
                    timeout=30.0
                )
                elapsed = (time.time() - start) * 1000
                latencies.append(elapsed)
            except Exception as e:
                print(f"Request {i} failed: {e}")
    
    latencies.sort()
    n = len(latencies)
    
    print(f"P50: {latencies[int(n*0.5)]:.1f}ms")
    print(f"P95: {latencies[int(n*0.95)]:.1f}ms")
    print(f"P99: {latencies[int(n*0.99)]:.1f}ms")
    print(f"Mean: {statistics.mean(latencies):.1f}ms")
    print(f"Max: {max(latencies):.1f}ms")
    print(f"Total requests: {n}")
    
    # Assert targets
    p50 = latencies[int(n*0.5)]
    p95 = latencies[int(n*0.95)]
    p99 = latencies[int(n*0.99)]
    
    print("\n=== Targets ===")
    print(f"P50: {p50:.1f}ms < 200ms: {'✅ PASS' if p50 < 200 else '❌ FAIL'}")
    print(f"P95: {p95:.1f}ms < 800ms: {'✅ PASS' if p95 < 800 else '❌ FAIL'}")
    print(f"P99: {p99:.1f}ms < 1200ms: {'✅ PASS' if p99 < 1200 else '❌ FAIL'}")
    
    assert p50 < 200, f"P50 too high: {p50}ms"
    assert p95 < 800, f"P95 too high: {p95}ms"
    assert p99 < 1200, f"P99 too high: {p99}ms"
    
    print("\n✅ All latency targets met!")

if __name__ == "__main__":
    asyncio.run(benchmark_latency())
