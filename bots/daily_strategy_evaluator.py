#!/usr/bin/env python3
"""
Daily Strategy Evaluator
Evaluates newly extracted strategies from video titles/descriptions,
ranks them by projected profitability, and updates bot configurations
automatically. Designed to run as a scheduled cron job.
"""
import json
import os
import logging
from datetime import datetime
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler('/home/sergio/denaro/logs/daily_evaluator.log')
    ]
)

# Paths
STRATEGIES_MD = '/home/sergio/denaro/strategies_extracted.md'
CONFIG_DIR = '/home/sergio/denaro/squadra/config'
REPORTS_DIR = '/home/sergio/denaro/reports'

# Ensure directories exist
Path(REPORTS_DIR).mkdir(parents=True, exist_ok=True)

def extract_new_strategies():
    """Parse strategies_extracted.md and return a list of new strategy entries."""
    if not os.path.exists(STRATEGIES_MD):
        logging.warning('Strategies file not found: %s', STRATEGIES_MD)
        return []
    
    with open(STRATEGIES_MD, 'r') as f:
        content = f.read()
    
    # Simple heuristic: capture bullet points under "## 1. Strategie di Trading Automatico"
    sections = content.split('##')[1:]  # Skip title line
    new_strategies = []
    for section in sections:
        if 'Strategie di Trading Automatico' in section:
            # Extract lines that look like strategy items
            lines = section.split('\n')
            for line in lines:
                if line.strip().startswith('- **'):
                    # Basic parsing: extract bolded text as strategy name
                    strategy = line.strip().split('**')[1].strip()
                    new_strategies.append(strategy)
    return new_strategies

def evaluate_strategy_profitability(strategy_name: str) -> float:
    """
    Very basic profitability estimator:
    - Keywords like 'arbitrage', 'gaussian', 'ai' get higher scores
    - Longer descriptions get slightly higher scores
    Returns a float score between 0 and 1.
    """
    # In a real system this would use more sophisticated heuristics
    score = 0.0
    lowered = strategy_name.lower()
    if 'arbitrage' in lowered:
        score += 0.3
    if 'gaussian' in lowered:
        score += 0.2
    if 'ai' in lowered or 'neural' in lowered:
        score += 0.2
    if 'momentum' in lowered or 'scalping' in lowered:
        score += 0.1
    # Rough length weighting
    if len(strategy_name) > 10:
        score += 0.1
    return min(score, 1.0)

def update_bot_configurations(strategies: list):
    """Update JSON config files for bots based on evaluated strategies."""
    for strategy in strategies:
        score = evaluate_strategy_profitability(strategy)
        logging.info('Strategy "%s" scored %0.2f for prioritization', strategy, score)
        
        # Example: map high-score strategies to specific bot configs
        if score >= 0.6:
            # Prioritize risk settings relaxation (already handled via drawdown updates)
            logging.info('Strategy "%s" eligible for enhanced risk parameters', strategy)
        # In a full implementation, this would modify JSON configs dynamically
    # Write a simple report
    report_path = f'{REPORTS_DIR}/strategy_evaluation_{datetime.now().strftime("%Y%m%d")}.json'
    with open(report_path, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'evaluated_strategies': [
                {'name': s, 'score': evaluate_strategy_profitability(s)}
                for s in strategies
            ]
        }, f, indent=2)
    logging.info('Daily evaluation report written to %s', report_path)

def main():
    logging.info('=== Daily Strategy Evaluation Started ===')
    strategies = extract_new_strategies()
    if not strategies:
        logging.info('No new strategies found')
        return
    logging.info('Found %d new strategies', len(strategies))
    update_bot_configurations(strategies)
    logging.info('=== Daily Strategy Evaluation Completed ===')

if __name__ == '__main__':
    main()