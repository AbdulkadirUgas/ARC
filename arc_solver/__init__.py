"""
Neuro-Symbolic ARC Solver - Main Package

A production-ready Python system for solving ARC-AGI tasks using
a Reasoning → Coding → Verification loop.

Classes:
    NeuroSymbolicAgent: Main agent for solving ARC tasks
    TaskSolution: Result of solving a task

Functions:
    load_task_file: Load task from JSON
    run_verification: Execute and verify code
"""

from agent import NeuroSymbolicAgent, TaskSolution
from main import load_task_file, print_solution_summary
from sandbox import run_verification, run_test_inference

__version__ = "1.0.0"
__author__ = "Principal AI Architect"
__all__ = [
    "NeuroSymbolicAgent",
    "TaskSolution",
    "load_task_file",
    "run_verification",
    "run_test_inference",
    "print_solution_summary",
]
