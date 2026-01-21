# SPDX-FileCopyrightText: 2022 Konstantinos Thoukydidis <mail@dbzer0.com>
# SPDX-FileCopyrightText: 2024 AI Power Grid Contributors
#
# SPDX-License-Identifier: AGPL-3.0-or-later

"""
CSAM Prompt Checker for ComfyUI Bridge

This module implements prompt-based content safety filtering to detect and block
potentially harmful content involving minors. Based on the detection system used
in the AI Power Grid / Horde infrastructure.

The checker uses multiple layers of detection:
1. Regex-based keyword detection for CSAM-related terms
2. Emoji detection for child-related emojis
3. Age-reference detection (e.g., "X years old" for minors)
4. NSFW model prompt replacement to convert suspicious terms

Reference: https://github.com/AIPowerGrid/image-worker
"""

import logging
import re
from typing import Tuple, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PromptCheckResult:
    """Result of a prompt safety check."""
    suspicion_level: int  # 0 = safe, 1+ = suspicious
    matched_terms: List[str]  # Terms that triggered the detection
    blocked: bool  # Whether the prompt should be blocked
    sanitized_prompt: Optional[str]  # Sanitized version of the prompt (if applicable)
    reason: str  # Human-readable reason


class PromptChecker:
    """
    Checks prompts for CSAM-related content.
    
    Uses multiple detection methods:
    - Keyword regex matching for suspicious terms
    - Emoji detection for child-related emojis
    - Age reference detection
    - NSFW model prompt sanitization
    
    NOTE: This filter is ALWAYS enabled and cannot be disabled.
    CSAM protection is mandatory for all image generation.
    """
    
    def __init__(self, enabled: bool = True):
        # CSAM filtering is ALWAYS enabled - parameter ignored for safety
        self.enabled = True  # Hardcoded - cannot be disabled
        
        # Primary CSAM detection regex patterns
        # These match terms commonly associated with minor-related content
        self.csam_keywords = re.compile(
            r"\b(loli|shota|pedo|child\s*porn|cp\b|preteen|"
            r"underage\s*(girl|boy|sex|nude|naked)|"
            r"minor\s*(sex|nude|naked|porn)|"
            r"kid\s*(sex|nude|naked|porn)|"
            r"toddler\s*(sex|nude|naked)|"
            r"infant\s*(sex|nude|naked)|"
            r"baby\s*(sex|nude|naked))\b",
            re.IGNORECASE
        )
        
        # Age-based CSAM triggers (e.g., "5 years old", "12 year old")
        # Matches ages 0-17 with "years old" pattern
        self.csam_age_triggers = re.compile(
            r"\b(0?[0-9]|1[0-7])(?![0-9])\s*years?\s*old\b",
            re.IGNORECASE
        )
        
        # Terms that should be replaced when used with NSFW models
        # to prevent generating inappropriate content
        self.nsfw_replacement_patterns = [
            {
                "regex": re.compile(r"\bstudent\b|\byoung\b|\blit[tl]?le\b|\blil\b|\bsmall\b|\btiny\b", re.IGNORECASE),
                "replacement": "adult",
            },
            {
                "regex": re.compile(r"\bgirl\b|\bnina\b", re.IGNORECASE),
                "replacement": "adult woman",
            },
            {
                "regex": re.compile(r"\bboys?\b|\bsons?\b", re.IGNORECASE),
                "replacement": "adult man",
            },
            {
                "regex": re.compile(r"\bchild\b|\bchildren\b|\bkid\b|\bkids\b", re.IGNORECASE),
                "replacement": "adult person",
            },
            {
                "regex": re.compile(r"\bteen\b|\bteenager\b|\bteens\b", re.IGNORECASE),
                "replacement": "adult",
            },
            {
                "regex": re.compile(r"\bdaughter\b", re.IGNORECASE),
                "replacement": "adult woman",
            },
        ]
        
        # Child-related emojis that trigger suspicion
        self.child_emojis = {
            "👧", "👧🏻", "👧🏼", "👧🏽", "👧🏾", "👧🏿",  # Girl
            "👦", "👦🏻", "👦🏼", "👦🏽", "👦🏾", "👦🏿",  # Boy
            "👶", "👶🏻", "👶🏼", "👶🏽", "👶🏾", "👶🏿",  # Baby
            "👼", "👼🏻", "👼🏼", "👼🏽", "👼🏾", "👼🏿",  # Baby angel
            "🧒", "🧒🏻", "🧒🏼", "🧒🏽", "🧒🏾", "🧒🏿",  # Child
            "👪",  # Family
            "🤱", "🤱🏻", "🤱🏼", "🤱🏽", "🤱🏾", "🤱🏿",  # Breastfeeding
            "🍼",  # Baby bottle
            "🚼",  # Baby symbol
            "🚸",  # Children crossing
        }
        
        # Prompt normalization patterns
        self.weight_remover = re.compile(r"\((.*?):\d+\.?\d*\)")
        self.whitespace_normalizer = re.compile(r"\s+")
        self.special_char_remover = re.compile(r"[^\w\s]")
        
        logger.info(f"CSAM Prompt Checker initialized (enabled={enabled})")
    
    def normalize_prompt(self, prompt: str) -> str:
        """
        Normalize prompt for scanning by removing tricks used to avoid filters.
        
        - Removes prompt weights like (word:1.5)
        - Normalizes whitespace
        - Handles special characters
        """
        # Remove prompt weights
        normalized = self.weight_remover.sub(r"\1", prompt)
        # Replace special chars with spaces
        normalized = self.special_char_remover.sub(" ", normalized)
        # Normalize whitespace
        normalized = self.whitespace_normalizer.sub(" ", normalized).strip()
        return normalized.lower()
    
    def check_prompt(self, prompt: str) -> PromptCheckResult:
        """
        Check a prompt for CSAM-related content.
        
        Args:
            prompt: The prompt to check
            
        Returns:
            PromptCheckResult with suspicion level and details
        
        NOTE: This check is ALWAYS performed - CSAM filtering cannot be bypassed.
        """
        # No bypass - CSAM filtering is mandatory
        
        matched_terms = []
        suspicion_level = 0
        
        # Split prompt and negative prompt
        if "###" in prompt:
            positive_prompt, negative_prompt = prompt.split("###", 1)
        else:
            positive_prompt = prompt
            negative_prompt = ""
        
        normalized = self.normalize_prompt(positive_prompt)
        
        # Check for explicit CSAM keywords (immediate block)
        csam_match = self.csam_keywords.search(normalized)
        if csam_match:
            matched_terms.append(csam_match.group())
            logger.warning(f"🚫 CSAM keyword detected: {csam_match.group()}")
            return PromptCheckResult(
                suspicion_level=10,  # Maximum suspicion
                matched_terms=matched_terms,
                blocked=True,
                sanitized_prompt=None,
                reason=f"CSAM keyword detected: {csam_match.group()}"
            )
        
        # Check for age-based CSAM triggers
        age_match = self.csam_age_triggers.search(normalized)
        if age_match:
            matched_terms.append(age_match.group())
            suspicion_level += 2
            logger.warning(f"⚠️ Minor age reference detected: {age_match.group()}")
        
        # Check for child-related emojis in original prompt
        for emoji in self.child_emojis:
            if emoji in prompt:
                matched_terms.append(f"emoji:{emoji}")
                suspicion_level += 1
                logger.info(f"Child-related emoji detected: {emoji}")
                break  # Only count once
        
        # Determine if prompt should be blocked
        blocked = suspicion_level >= 3  # Block if suspicion level is high
        
        if blocked:
            return PromptCheckResult(
                suspicion_level=suspicion_level,
                matched_terms=matched_terms,
                blocked=True,
                sanitized_prompt=None,
                reason=f"High suspicion level ({suspicion_level}): {', '.join(matched_terms)}"
            )
        
        return PromptCheckResult(
            suspicion_level=suspicion_level,
            matched_terms=matched_terms,
            blocked=False,
            sanitized_prompt=None,
            reason="Prompt passed safety check" if suspicion_level == 0 else f"Low suspicion ({suspicion_level})"
        )
    
    def sanitize_nsfw_prompt(self, prompt: str) -> Tuple[str, bool]:
        """
        Sanitize a prompt for use with NSFW models by replacing
        terms that could generate inappropriate content.
        
        Args:
            prompt: The prompt to sanitize
            
        Returns:
            Tuple of (sanitized_prompt, was_modified)
        
        NOTE: This sanitization is ALWAYS available - CSAM protection cannot be bypassed.
        """
        
        # Split prompt and negative prompt
        negative_prompt = ""
        if "###" in prompt:
            prompt, negative_prompt = prompt.split("###", 1)
            negative_prompt = "###" + negative_prompt
        
        original_prompt = prompt
        
        # Apply replacement patterns
        for pattern in self.nsfw_replacement_patterns:
            prompt = pattern["regex"].sub(pattern["replacement"], prompt)
        
        was_modified = prompt != original_prompt
        
        if was_modified:
            # Add safety negative prompts
            safety_negatives = "child, infant, underage, immature, teenager, tween, minor, young"
            if negative_prompt:
                negative_prompt = f"###{safety_negatives}, " + negative_prompt[3:]
            else:
                negative_prompt = f"###{safety_negatives}"
            
            logger.info(f"Prompt sanitized for NSFW model safety")
            logger.debug(f"Original: {original_prompt[:100]}...")
            logger.debug(f"Sanitized: {prompt[:100]}...")
        
        return prompt + negative_prompt, was_modified
    
    def check_and_process(self, prompt: str, is_nsfw_model: bool = False) -> PromptCheckResult:
        """
        Check a prompt and optionally sanitize it for NSFW models.
        
        Args:
            prompt: The prompt to check
            is_nsfw_model: Whether this is for an NSFW-capable model
            
        Returns:
            PromptCheckResult with full details
        """
        # First, do the safety check
        result = self.check_prompt(prompt)
        
        if result.blocked:
            return result
        
        # If using NSFW model and there's any suspicion, sanitize
        if is_nsfw_model and result.suspicion_level > 0:
            sanitized, was_modified = self.sanitize_nsfw_prompt(prompt)
            if was_modified:
                result.sanitized_prompt = sanitized
                result.reason = f"Prompt sanitized for NSFW model: {result.reason}"
        
        return result


# Singleton instance
_prompt_checker: Optional[PromptChecker] = None


def get_prompt_checker() -> PromptChecker:
    """Get the global prompt checker instance."""
    global _prompt_checker
    
    if _prompt_checker is None:
        from .config import Settings
        enabled = getattr(Settings, 'CSAM_FILTER_ENABLED', True)
        _prompt_checker = PromptChecker(enabled=enabled)
    
    return _prompt_checker


def check_prompt_safety(prompt: str, is_nsfw_model: bool = False) -> PromptCheckResult:
    """
    Convenience function to check prompt safety.
    
    Args:
        prompt: The prompt to check
        is_nsfw_model: Whether this is for an NSFW-capable model
        
    Returns:
        PromptCheckResult with verdict and details
    """
    checker = get_prompt_checker()
    return checker.check_and_process(prompt, is_nsfw_model)
