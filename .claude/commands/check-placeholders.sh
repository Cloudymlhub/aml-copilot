#!/bin/bash
# Check Placeholder Content - Find all MOCK_DATA and PLACEHOLDER markers
#
# Usage: ./check-placeholders.sh [priority]
#   priority: Optional filter (HIGH, MEDIUM, LOW)
#
# Examples:
#   ./check-placeholders.sh        # Show all
#   ./check-placeholders.sh HIGH   # Show only HIGH priority

set -euo pipefail

PRIORITY_FILTER="${1:-}"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

cd "$PROJECT_ROOT"

echo "PLACEHOLDER CONTENT INVENTORY"
echo "=============================="
echo ""

# Function to search and categorize
search_placeholders() {
    local priority="$1"
    local pattern="$2"
    local count=0

    echo "$priority PRIORITY"
    echo "$(printf '%.0s-' {1..50})"

    while IFS= read -r line; do
        file=$(echo "$line" | cut -d: -f1)
        content=$(echo "$line" | cut -d: -f2-)

        # Extract brief description
        description=$(echo "$content" | sed -E 's/^[[:space:]]*(MOCK_DATA|PLACEHOLDER):[[:space:]]*//' | sed -E 's/[[:space:]]*-[[:space:]]*Priority:.*//')

        echo "$((++count)). $file"
        echo "   $description"
        echo ""
    done < <(grep -rE "$pattern" --include="*.py" . | sort)

    if [ $count -eq 0 ]; then
        echo "None found"
        echo ""
    fi

    echo "$count items"
    echo ""
}

# If priority filter specified, show only that priority
if [ -n "$PRIORITY_FILTER" ]; then
    search_placeholders "$PRIORITY_FILTER" "(MOCK_DATA|PLACEHOLDER).*$PRIORITY_FILTER"
else
    # Show all, categorized by priority
    search_placeholders "HIGH" "(MOCK_DATA|PLACEHOLDER).*HIGH"
    search_placeholders "MEDIUM" "(MOCK_DATA|PLACEHOLDER).*MEDIUM"
    search_placeholders "LOW" "(MOCK_DATA|PLACEHOLDER).*LOW"
fi

# Summary
echo "SUMMARY"
echo "======="
total=$(grep -rE "(MOCK_DATA|PLACEHOLDER)" --include="*.py" . | wc -l | tr -d ' ')
high=$(grep -rE "(MOCK_DATA|PLACEHOLDER).*HIGH" --include="*.py" . | wc -l | tr -d ' ')
medium=$(grep -rE "(MOCK_DATA|PLACEHOLDER).*MEDIUM" --include="*.py" . | wc -l | tr -d ' ')
low=$(grep -rE "(MOCK_DATA|PLACEHOLDER).*LOW" --include="*.py" . | wc -l | tr -d ' ')

echo "Total markers: $total"
echo "High: $high | Medium: $medium | Low: $low"
echo ""

# Breakdown by type
mock_count=$(grep -r "MOCK_DATA" --include="*.py" . | wc -l | tr -d ' ')
placeholder_count=$(grep -r "PLACEHOLDER" --include="*.py" . | wc -l | tr -d ' ')

echo "Mock Data (synthetic/will replace): $mock_count"
echo "Placeholders (needs expert review): $placeholder_count"
echo ""

# Next steps
echo "NEXT STEPS"
echo "=========="

if [ "$high" -gt 0 ]; then
    echo "⚠️  $high HIGH priority items require immediate attention before production:"
    echo "   - Schedule AML compliance expert review"
    echo "   - Schedule legal/regulatory team review"
    echo "   - Implement ML model service integration"
    echo ""
fi

if [ "$placeholder_count" -gt 0 ]; then
    echo "📋 $placeholder_count items need expert review/validation:"
    echo "   - See docs/PLACEHOLDER_CONTENT_TRACKER.md for review process"
    echo "   - Contact domain experts to schedule reviews"
    echo ""
fi

if [ "$mock_count" -gt 0 ]; then
    echo "🔄 $mock_count mock data items need production implementation:"
    echo "   - Integrate with ML model service"
    echo "   - Configure production data sources"
    echo ""
fi

echo "For detailed information, see:"
echo "  docs/PLACEHOLDER_CONTENT_TRACKER.md"
