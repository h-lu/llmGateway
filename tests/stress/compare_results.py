"""Compare before/after optimization results from Locust CSV files."""

import csv
import sys
from pathlib import Path

def load_stats(filename):
    """Load final aggregated stats from CSV."""
    with open(filename) as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['Type'] == 'Aggregated':
                return row
    return None

def format_improvement(before, after):
    """Calculate improvement percentage."""
    try:
        b = float(before)
        a = float(after)
        improvement = ((b - a) / b) * 100
        return f"{improvement:+.1f}%"
    except (ValueError, ZeroDivisionError):
        return "N/A"

def main():
    # Find result files
    reports_dir = Path(__file__).parent / "reports"
    
    before_files = list(reports_dir.glob("locust_300users_20min_*_stats.csv"))
    after_files = list(reports_dir.glob("locust_300users_optimized_stats.csv"))
    
    if not before_files:
        print("Error: No 'before' results found")
        sys.exit(1)
    
    # Use most recent before file
    before_file = sorted(before_files)[-1]
    before = load_stats(before_file)
    
    print("="*70)
    print("P95/P99 延迟优化效果对比")
    print("="*70)
    print(f"Before: {before_file.name}")
    
    if after_files:
        after_file = after_files[0]
        after = load_stats(after_file)
        print(f"After:  {after_file.name}")
        
        print("\n" + "-"*70)
        print(f"{'指标':<20} {'优化前':<15} {'优化后':<15} {'改善':<15}")
        print("-"*70)
        
        metrics = [
            ('平均延迟(ms)', 'Total Average Response Time'),
            ('P50(ms)', '50%'),
            ('P95(ms)', '95%'),
            ('P99(ms)', '99%'),
            ('RPS', 'Requests/s'),
        ]
        
        for label, key in metrics:
            b = before[key]
            a = after[key]
            imp = format_improvement(b, a)
            print(f"{label:<20} {float(b):<15.1f} {float(a):<15.1f} {imp:<15}")
        
        print("="*70)
        
        # Overall assessment
        p95_before = float(before['95%'])
        p95_after = float(after['95%'])
        improvement = ((p95_before - p95_after) / p95_before) * 100
        
        print(f"\nP95 延迟改善: {improvement:.1f}%")
        if improvement > 30:
            print("🎉 优化效果显著！")
        elif improvement > 10:
            print("✅ 优化效果良好")
        else:
            print("⚠️ 优化效果有限")
    else:
        print("\nNo 'after' results yet. Run locust test to generate:")
        print("locust -f tests/stress/locustfile_long.py --headless --users 300 --run-time 20m")

if __name__ == "__main__":
    main()
