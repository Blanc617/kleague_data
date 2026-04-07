"""
Structured data query engine for K-League match data.
Queries JSON files directly — no hallucination possible.
"""
from data_engine.match_data_engine import MatchDataEngine
from data_engine.query_classifier import QueryClassifier, QueryType
from data_engine.player_comparison import PlayerComparisonEngine

__all__ = ["MatchDataEngine", "QueryClassifier", "QueryType", "PlayerComparisonEngine"]
