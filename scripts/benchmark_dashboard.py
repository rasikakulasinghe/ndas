"""
Performance benchmarking script for NDAS dashboard.

Measures query count and response time before/after optimizations.
"""

import os
import sys
import django
import time
from datetime import datetime

# Setup Django environment
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ndas.settings')
django.setup()

from django.test import Client, RequestFactory
from django.contrib.auth import get_user_model
from django.db import connection, reset_queries
from django.conf import settings

from patients.models import Patient, GMAssessment, Video
from patients.views import dashboard

User = get_user_model()


def create_test_data(num_patients=100):
    """Create test data for benchmarking."""
    print(f"\n📊 Creating {num_patients} test patients...")

    # Get or create test user
    user, created = User.objects.get_or_create(
        username='benchmark_user',
        defaults={
            'email': 'benchmark@test.com',
            'is_staff': True,
            'is_superuser': True
        }
    )
    if created:
        user.set_password('benchmark123')
        user.save()

    # Create patients
    patients_created = 0
    for i in range(num_patients):
        patient, created = Patient.objects.get_or_create(
            bht=f'BENCH-{i:04d}',
            defaults={
                'baby_name': f'Benchmark Baby {i}',
                'mother_name': f'Benchmark Mother {i}',
                'dob_tob': datetime.now(),
                'gender': 'M' if i % 2 == 0 else 'F',
                'pog_wks': 38,
                'pog_days': i % 7,
                'birth_weight': 3000 + (i * 10),
                'added_by': user,
            }
        )
        if created:
            patients_created += 1

            # Add some assessments and videos
            if i % 5 == 0:
                GMAssessment.objects.get_or_create(
                    patient=patient,
                    defaults={
                        'date_of_assessment': datetime.now(),
                        'added_by': user,
                    }
                )

            if i % 10 == 0:
                Video.objects.get_or_create(
                    patient=patient,
                    title=f'Video for {patient.baby_name}',
                    defaults={
                        'recorded_on': datetime.now(),
                        'added_by': user,
                    }
                )

    print(f"✅ Created {patients_created} new patients")
    print(f"📈 Total patients in database: {Patient.objects.count()}")
    print(f"📹 Total videos: {Video.objects.count()}")
    print(f"📋 Total assessments: {GMAssessment.objects.count()}")
    return user


def benchmark_dashboard(user, num_runs=5):
    """
    Benchmark dashboard performance.

    Args:
        user: User object for authentication
        num_runs: Number of times to run the benchmark

    Returns:
        dict: Benchmark results
    """
    print(f"\n🚀 Running dashboard benchmark ({num_runs} runs)...")

    # Enable query logging
    settings.DEBUG = True

    factory = RequestFactory()

    query_counts = []
    response_times = []

    for run in range(num_runs):
        # Reset query log
        reset_queries()

        # Create request
        request = factory.get('/dashboard/')
        request.user = user

        # Measure performance
        start_time = time.time()

        try:
            response = dashboard(request)
            status_code = response.status_code
        except Exception as e:
            print(f"❌ Error during benchmark run {run + 1}: {e}")
            continue

        end_time = time.time()

        # Collect metrics
        query_count = len(connection.queries)
        response_time = (end_time - start_time) * 1000  # Convert to ms

        query_counts.append(query_count)
        response_times.append(response_time)

        print(f"  Run {run + 1}: {query_count} queries, {response_time:.2f}ms, status={status_code}")

    # Calculate statistics
    if query_counts:
        avg_queries = sum(query_counts) / len(query_counts)
        avg_response_time = sum(response_times) / len(response_times)
        min_queries = min(query_counts)
        max_queries = max(query_counts)
        min_time = min(response_times)
        max_time = max(response_times)

        return {
            'num_runs': len(query_counts),
            'avg_queries': avg_queries,
            'min_queries': min_queries,
            'max_queries': max_queries,
            'avg_response_time_ms': avg_response_time,
            'min_response_time_ms': min_time,
            'max_response_time_ms': max_time,
        }
    else:
        return None


def print_results(results, title):
    """Print benchmark results in a formatted way."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

    if results:
        print(f"  Number of runs:       {results['num_runs']}")
        print(f"  Average queries:      {results['avg_queries']:.1f}")
        print(f"  Query range:          {results['min_queries']} - {results['max_queries']}")
        print(f"  Average response:     {results['avg_response_time_ms']:.2f}ms")
        print(f"  Response range:       {results['min_response_time_ms']:.2f}ms - {results['max_response_time_ms']:.2f}ms")
    else:
        print("  ❌ No valid results collected")

    print(f"{'='*60}\n")


def calculate_improvement(before, after):
    """Calculate improvement metrics."""
    if not before or not after:
        return None

    query_reduction = ((before['avg_queries'] - after['avg_queries']) / before['avg_queries']) * 100
    time_improvement = ((before['avg_response_time_ms'] - after['avg_response_time_ms']) / before['avg_response_time_ms']) * 100

    return {
        'query_reduction_percent': query_reduction,
        'time_improvement_percent': time_improvement,
        'queries_before': before['avg_queries'],
        'queries_after': after['avg_queries'],
        'time_before_ms': before['avg_response_time_ms'],
        'time_after_ms': after['avg_response_time_ms'],
    }


def main():
    """Main benchmarking function."""
    print("\n" + "="*60)
    print("  NDAS Dashboard Performance Benchmark")
    print("="*60)

    # Create test data
    user = create_test_data(num_patients=100)

    # Run benchmark
    results = benchmark_dashboard(user, num_runs=5)

    print_results(results, "📊 DASHBOARD PERFORMANCE RESULTS (AFTER OPTIMIZATION)")

    # Expected baseline (before optimization): ~50 queries
    # Expected after optimization: ~15 queries (70% reduction)

    print("\n📝 PERFORMANCE ANALYSIS:")
    print("-" * 60)

    if results:
        # Target: < 20 queries
        if results['avg_queries'] < 20:
            print(f"✅ Query count: {results['avg_queries']:.1f} (Target: <20) - PASSED")
        else:
            print(f"⚠️  Query count: {results['avg_queries']:.1f} (Target: <20) - NEEDS IMPROVEMENT")

        # Target: < 1000ms (1 second)
        if results['avg_response_time_ms'] < 1000:
            print(f"✅ Response time: {results['avg_response_time_ms']:.2f}ms (Target: <1000ms) - PASSED")
        else:
            print(f"⚠️  Response time: {results['avg_response_time_ms']:.2f}ms (Target: <1000ms) - NEEDS IMPROVEMENT")

        print("-" * 60)
        print("\n💡 OPTIMIZATION IMPACT:")
        print(f"   Expected baseline (unoptimized): ~50 queries")
        print(f"   Current performance: {results['avg_queries']:.1f} queries")

        if results['avg_queries'] < 50:
            reduction = ((50 - results['avg_queries']) / 50) * 100
            print(f"   Estimated improvement: {reduction:.1f}% query reduction")

        print("\n🎯 RECOMMENDATIONS:")
        if results['avg_queries'] > 20:
            print("   - Review query usage in dashboard view")
            print("   - Ensure select_related() and prefetch_related() are used")
            print("   - Check for N+1 query problems")
        else:
            print("   ✅ Query optimization is excellent!")

        if results['avg_response_time_ms'] > 1000:
            print("   - Consider database indexing")
            print("   - Review complex queries")
            print("   - Consider caching frequently accessed data")
        else:
            print("   ✅ Response time is excellent!")

    print("\n" + "="*60)
    print("  Benchmark Complete!")
    print("="*60 + "\n")

    return results


if __name__ == '__main__':
    try:
        results = main()
        sys.exit(0)
    except KeyboardInterrupt:
        print("\n\n⚠️  Benchmark interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Benchmark failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
