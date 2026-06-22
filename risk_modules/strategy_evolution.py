"""
Automated Strategy Evolution – Genetic algorithm for parameter optimization.
"""
import logging, random, copy, math
from typing import Dict, List, Any, Optional

class StrategyEvolution:
    def __init__(self):
        self.logger = logging.getLogger("StrategyEvolution")
        self.population_size = 10
        self.mutation_rate = 0.1
        self.crossover_rate = 0.7
        self.elite_size = 2
        
    def create_individual(self, base_params: Dict) -> Dict:
        """Create a mutated individual from base parameters."""
        individual = copy.deepcopy(base_params)
        
        # Mutate numeric parameters
        for key, value in individual.items():
            if isinstance(value, (int, float)) and key != "seed":
                if random.random() < self.mutation_rate:
                    # Gaussian mutation
                    if isinstance(value, int):
                        individual[key] = max(1, value + random.randint(-2, 2))
                    else:
                        # 10% relative change
                        individual[key] = value * (1 + random.uniform(-0.1, 0.1))
                        
        return individual
    
    def crossover(self, parent1: Dict, parent2: Dict) -> Dict:
        """Create offspring by combining two parents."""
        child = {}
        for key in parent1:
            if key in parent2:
                if random.random() < self.crossover_rate:
                    # Average for floats, random choice for ints
                    if isinstance(parent1[key], float) and isinstance(parent2[key], float):
                        child[key] = (parent1[key] + parent2[key]) / 2
                    else:
                        child[key] = random.choice([parent1[key], parent2[key]])
                else:
                    child[key] = parent1[key]
            else:
                child[key] = parent1[key]
        return child
    
    def evaluate_fitness(self, params: Dict, backtest_results: Dict) -> float:
        """
        Fitness function for a parameter set.
        Returns a score (higher is better).
        """
        if not backtest_results:
            return 0.0
            
        sharpe = backtest_results.get("sharpe", 0)
        win_rate = backtest_results.get("win_rate", 0)
        max_dd = backtest_results.get("max_drawdown", 100)
        total_return = backtest_results.get("total_return", 0)
        
        # Weighted fitness
        fitness = (
            sharpe * 0.4 +
            win_rate * 0.3 +
            (100 - max_dd) * 0.2 +
            total_return * 0.1
        )
        
        return max(0.0, fitness)
    
    def evolve_generation(self, population: List[Dict], fitness_scores: List[float]) -> List[Dict]:
        """Create next generation via selection, crossover, mutation."""
        if len(population) != len(fitness_scores):
            return population
            
        # Sort by fitness
        sorted_pop = [p for _, p in sorted(zip(fitness_scores, population), key=lambda x: x[0], reverse=True)]
        
        # Keep elites
        new_pop = sorted_pop[:self.elite_size]
        
        # Fill rest with offspring
        while len(new_pop) < self.population_size:
            # Tournament selection
            parent1 = self._tournament_selection(sorted_pop, fitness_scores)
            parent2 = self._tournament_selection(sorted_pop, fitness_scores)
            
            # Crossover
            child = self.crossover(parent1, parent2)
            
            # Mutation
            if random.random() < self.mutation_rate:
                child = self.mutate(child)
            
            new_pop.append(child)
            
        return new_pop
    
    def _tournament_selection(self, population: List[Dict], fitness_scores: List[float], tournament_size: int = 3) -> Dict:
        """Select parent via tournament."""
        indices = random.sample(range(len(population)), min(tournament_size, len(population)))
        best_idx = max(indices, key=lambda i: fitness_scores[i])
        return population[best_idx]
    
    def mutate(self, individual: Dict) -> Dict:
        """Apply random mutations to individual."""
        mutated = copy.deepcopy(individual)
        for key, value in mutated.items():
            if isinstance(value, (int, float)) and key != "seed" and random.random() < self.mutation_rate:
                if isinstance(value, int):
                    mutated[key] = max(1, value + random.randint(-1, 1))
                else:
                    mutated[key] = value * (1 + random.uniform(-0.05, 0.05))
        return mutated
    
    def optimize(self, base_params: Dict, evaluate_fn, generations: int = 5) -> Dict:
        """
        Run evolutionary optimization.
        evaluate_fn(params) -> backtest_results dict with sharpe, win_rate, etc.
        """
        # Initialize population
        population = [self.create_individual(base_params) for _ in range(self.population_size)]
        
        for gen in range(generations):
            self.logger.info(f"Generation {gen + 1}/{generations}")
            
            # Evaluate all individuals
            fitness_scores = []
            for individual in population:
                try:
                    results = evaluate_fn(individual)
                    fitness = self.evaluate_fitness(individual, results)
                    fitness_scores.append(fitness)
                except Exception as e:
                    self.logger.error(f"Evaluation error: {e}")
                    fitness_scores.append(0.0)
            
            best_idx = fitness_scores.index(max(fitness_scores))
            self.logger.info(f"Best fitness: {fitness_scores[best_idx]:.4f}")
            
            # Create next generation
            if gen < generations - 1:
                population = self.evolve_generation(population, fitness_scores)
        
        # Return best individual
        return population[best_idx]