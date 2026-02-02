"""Tests for content classifier."""

import pytest

from gateway.app.services.content_classifier import CachePolicy, ContentClassifier


class TestContentClassifier:
    """Test content classification."""
    
    def test_code_block_no_cache(self):
        """Code blocks should not be cached."""
        prompt = "```python\ndef hello():\n    pass\n```"
        assert ContentClassifier.classify(prompt) == CachePolicy.NO_CACHE
    
    def test_inline_code_no_cache(self):
        """Inline code should not be cached."""
        prompt = "What does `print()` do?"
        assert ContentClassifier.classify(prompt) == CachePolicy.NO_CACHE
    
    def test_function_def_no_cache(self):
        """Function definitions should not be cached."""
        prompt = "def calculate_sum(a, b): return a + b"
        assert ContentClassifier.classify(prompt) == CachePolicy.NO_CACHE
    
    def test_student_id_no_cache(self):
        """Student IDs should not be cached."""
        prompt = "我的学号是 2024001234，帮我检查作业"
        assert ContentClassifier.classify(prompt) == CachePolicy.NO_CACHE
    
    def test_email_no_cache(self):
        """Emails should not be cached."""
        prompt = "Contact me at student@example.com"
        assert ContentClassifier.classify(prompt) == CachePolicy.NO_CACHE
    
    def test_concept_question_cache(self):
        """Concept questions should be cached."""
        prompt = "什么是递归函数？"
        assert ContentClassifier.classify(prompt) == CachePolicy.CACHE
    
    def test_what_is_question_cache(self):
        """'What is' questions should be cached."""
        prompt = "What is Python?"
        assert ContentClassifier.classify(prompt) == CachePolicy.CACHE
    
    def test_comparison_cache(self):
        """Comparison questions should be cached."""
        prompt = "Python和Java有什么区别？"
        assert ContentClassifier.classify(prompt) == CachePolicy.CACHE
    
    def test_error_question_no_cache(self):
        """Error-related questions should not be cached."""
        prompt = "这个报错怎么解决？Traceback: ..."
        assert ContentClassifier.classify(prompt) == CachePolicy.NO_CACHE
    
    def test_is_concept_question(self):
        """Test concept question detection."""
        assert ContentClassifier.is_concept_question("什么是面向对象？") is True
        assert ContentClassifier.is_concept_question("帮我调试这段代码") is False
    
    def test_empty_prompt_no_cache(self):
        """Empty or None prompts should not be cached."""
        assert ContentClassifier.classify("") == CachePolicy.NO_CACHE
        assert ContentClassifier.classify(None) == CachePolicy.NO_CACHE
    
    def test_empty_prompt_not_concept(self):
        """Empty or None prompts should not be concept questions."""
        assert ContentClassifier.is_concept_question("") is False
        assert ContentClassifier.is_concept_question(None) is False
