"""
Compliance Assessment Pipeline

A tool to check agent-customer conversations for FDCPA compliance
violations and classify customer situations (product loss, substandard
service, or other).

Modules:
    compliance_checker  - Rule-based compliance violation detection
    situation_classifier - Customer situation classification
    evaluator           - Evaluation pipeline with metrics
    llm_compliance      - Optional LLM-based compliance layer
    config              - Centralized configuration
    models              - Data models and contracts
"""
