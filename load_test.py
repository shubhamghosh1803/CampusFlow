
import argparse
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from statistics import mean


def send_request(url):
    start = time.perf_counter()

    try:
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "CampusFlow-LoadTest"}
        )

        with urllib.request.urlopen(request, timeout=30) as response:
            response.read()
            status = response.status

        success = 200 <= status < 400

    except Exception as error:
        status = str(error)
        success = False

    elapsed = time.perf_counter() - start
    return success, elapsed, status


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--requests", type=int, default=1000)
    parser.add_argument("--concurrency", type=int, default=20)
    args = parser.parse_args()

    print(f"Target: {args.url}")
    print(f"Requests: {args.requests}")
    print(f"Concurrent workers: {args.concurrency}")
    print("Testing...")

    results = []
    start = time.perf_counter()

    with ThreadPoolExecutor(
        max_workers=args.concurrency
    ) as executor:
        futures = [
            executor.submit(send_request, args.url)
            for _ in range(args.requests)
        ]

        for future in as_completed(futures):
            results.append(future.result())

    total_time = time.perf_counter() - start

    successes = sum(1 for r in results if r[0])
    failures = len(results) - successes
    latencies = [r[1] for r in results]

    print("\n===== LOAD TEST RESULTS =====")
    print(f"Total requests:       {len(results)}")
    print(f"Successful requests:  {successes}")
    print(f"Failed requests:      {failures}")
    print(f"Total time:           {total_time:.2f} seconds")
    print(f"Requests/second:      {len(results) / total_time:.2f}")
    print(f"Average latency:      {mean(latencies) * 1000:.2f} ms")
    print(f"Max latency:          {max(latencies) * 1000:.2f} ms")

    sorted_latencies = sorted(latencies)
    p95_index = max(0, int(0.95 * len(sorted_latencies)) - 1)
    print(f"P95 latency:          {sorted_latencies[p95_index] * 1000:.2f} ms")


if __name__ == "__main__":
    main()
