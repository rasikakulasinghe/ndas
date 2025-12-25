#!/bin/bash
# NDAS Django Project Status Line
# Professional status line showing project context

# Read JSON input from stdin
input=$(cat)

# Extract key information
project_dir=$(echo "$input" | jq -r '.workspace.project_dir // empty')
current_dir=$(echo "$input" | jq -r '.workspace.current_dir // empty')
model_name=$(echo "$input" | jq -r '.model.display_name // "Unknown Model"')
output_style=$(echo "$input" | jq -r '.output_style.name // "default"')

# Calculate context window percentage (using current_usage, not cumulative totals)
usage=$(echo "$input" | jq '.context_window.current_usage')
if [ "$usage" != "null" ]; then
    current=$(echo "$usage" | jq '.input_tokens + .cache_creation_input_tokens + .cache_read_input_tokens')
    size=$(echo "$input" | jq '.context_window.context_window_size')
    pct=$((current * 100 / size))
    context_info="${pct}%"
else
    context_info="0%"
fi

# Get relative directory path
if [ -n "$project_dir" ] && [ -n "$current_dir" ]; then
    # Try to make path relative to project root
    rel_dir=$(echo "$current_dir" | sed "s|^$project_dir||" | sed 's|^/||' | sed 's|^\\||')
    if [ -z "$rel_dir" ]; then
        rel_dir="/"
    fi
else
    rel_dir=$(basename "$current_dir" 2>/dev/null || echo "~")
fi

# Get git branch (skip optional locks with --no-optional-locks)
git_branch=""
if [ -n "$current_dir" ]; then
    cd "$current_dir" 2>/dev/null
    if git rev-parse --git-dir > /dev/null 2>&1; then
        git_branch=$(git --no-optional-locks rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
        if [ -n "$git_branch" ]; then
            git_branch=" on \033[36m$git_branch\033[0m"
        fi
    fi
fi

# Build status line with dimmed colors
printf "\033[2m[\033[0m"
printf "\033[35m%s\033[0m" "$model_name"  # Magenta for model
printf "\033[2m | \033[0m"
printf "\033[33m%s\033[0m" "$output_style"  # Yellow for output style
printf "\033[2m | \033[0m"
printf "\033[32m%s\033[0m" "$rel_dir"  # Green for directory
printf "%s" "$git_branch"  # Cyan for branch (applied in variable)
printf "\033[2m | \033[0m"
printf "\033[34mctx: %s\033[0m" "$context_info"  # Blue for context
printf "\033[2m]\033[0m"
printf "\n"
