#!/usr/bin/env python3
"""
Research Idea Generation Evaluation Pipeline v4 cache variant
Uses cached Exa-retrieved predecessor contents from Sci-Reasoning repo results.
Keeps the official v4 generation, judge, parsing, and Hit@10 logic.

Author: Orchestra Agent
Date: 2026-01-04
"""

import os
import sys
import json
import time
import re
import argparse
import requests
from datetime import datetime
from pathlib import Path

# Add exa_py to path
sys.path.insert(0, '/tmp/exa_lib')

try:
    from exa_py import Exa
except ModuleNotFoundError:
    Exa = None

# Configuration
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(path):
    """Load simple KEY=VALUE lines without printing secret values."""
    if not path.exists():
        return
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_dotenv(PROJECT_ROOT / ".env")

EXA_API_KEY = os.getenv("EXA_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "")
MODEL_SLEEP_SECONDS = 0.0


def sanitize_api_error_text(text):
    """Remove configured secrets from provider error messages before logging."""
    sanitized = text
    for secret in (OPENAI_API_KEY, EXA_API_KEY):
        if secret and len(secret) >= 8:
            sanitized = sanitized.replace(secret, "[REDACTED_API_KEY]")
    return re.sub(r"(api_key:\s*)([A-Za-z0-9_\-]{24,})", r"\1[REDACTED_API_KEY]", sanitized)


DEFAULT_DATA_DIR = (
    PROJECT_ROOT
    / "Sci-Reasoning"
    / "research_idea_evaluation"
    / "projects"
    / "synthesis_graph_pipeline"
    / "results"
    / "conferences"
    / "NeurIPS-2025-oral"
)
DEFAULT_CONTEXT_CACHE = (
    PROJECT_ROOT
    / "Sci-Reasoning"
    / "research_idea_evaluation"
    / "results"
    / "evaluation_results_claude_sonnet_final.json"
)
CONTEXT_CACHE_PATH = DEFAULT_CONTEXT_CACHE
CONTEXT_CACHE_BY_TITLE = {}
CONTEXT_CACHE_SUMMARY = {}
OUTPUT_PATH = None

# Pricing for GPT-5.2
INPUT_COST_PER_1M = 2.0   # $2 per 1M input tokens
OUTPUT_COST_PER_1M = 14.0  # $14 per 1M output tokens

# Initialize Exa client
exa = Exa(api_key=EXA_API_KEY) if Exa is not None and EXA_API_KEY else None


def clean_title_for_search(title):
    """Clean paper title for better search results"""
    # Remove (Author et al., Year) patterns
    title = re.sub(r'\s*\([^)]*et al[^)]*\)', '', title)
    title = re.sub(r'\s*\([^)]*\d{4}[^)]*\)', '', title)
    # Remove [number] citations
    title = re.sub(r'\s*\[\d+\]', '', title)
    # Take first part before / or —
    title = re.split(r'\s*/\s*|—', title)[0]
    # Clean up whitespace
    title = re.sub(r'\s+', ' ', title).strip()
    return title


def is_quality_content(content):
    """Check if content is actual paper text, not just navigation/metadata"""
    if not content or len(content) < 200:
        return False
    
    # Check for arxiv boilerplate that indicates we got page chrome, not content
    boilerplate_indicators = [
        "Skip to main content",
        "Cornell University",
        "We gratefully acknowledge",
        "arXiv is a free distribution service",
        "arXiv.org e-Print archive",
    ]
    
    content_lower = content[:500].lower()
    boilerplate_count = sum(1 for b in boilerplate_indicators if b.lower() in content_lower)
    
    # If more than 1 boilerplate indicator in first 500 chars, likely bad content
    if boilerplate_count > 1:
        return False
    
    return True


def get_arxiv_html_content(arxiv_id, max_chars=10000):
    """Try to get content from arxiv HTML page directly"""
    html_url = f"https://arxiv.org/html/{arxiv_id}"
    
    try:
        result = exa.get_contents(
            [html_url],
            text={"max_characters": max_chars}
        )
        
        if result.results and result.results[0].text:
            content = result.results[0].text
            if is_quality_content(content):
                return content, html_url
    except Exception as e:
        pass
    
    return None, None


def extract_arxiv_id(url):
    """Extract arxiv ID from URL"""
    patterns = [
        r'arxiv\.org/abs/(\d+\.\d+)',
        r'arxiv\.org/html/(\d+\.\d+)',
        r'arxiv\.org/pdf/(\d+\.\d+)',
        r'arxiv\.org/abs/([a-z-]+/\d+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def search_paper_with_exa(title, max_chars=10000):
    """Search for a paper using Exa AI and retrieve content"""
    cleaned_title = clean_title_for_search(title)
    
    try:
        # Search with research paper category
        result = exa.search_and_contents(
            cleaned_title,
            type="auto",
            num_results=3,
            text={"max_characters": max_chars},
            category="research paper"
        )
        
        if result.results:
            for paper in result.results:
                content = paper.text or ""
                url = paper.url
                
                # Check if we got quality content
                if is_quality_content(content):
                    return {
                        "success": True,
                        "title": paper.title,
                        "url": url,
                        "content": content,
                        "original_query": title,
                        "cleaned_query": cleaned_title,
                        "content_quality": "good"
                    }
                
                # If arxiv URL but bad content, try HTML version
                arxiv_id = extract_arxiv_id(url)
                if arxiv_id:
                    html_content, html_url = get_arxiv_html_content(arxiv_id, max_chars)
                    if html_content:
                        return {
                            "success": True,
                            "title": paper.title,
                            "url": html_url,
                            "content": html_content,
                            "original_query": title,
                            "cleaned_query": cleaned_title,
                            "content_quality": "good_from_html"
                        }
            
            # Fallback: return first result even if quality is questionable
            paper = result.results[0]
            return {
                "success": True,
                "title": paper.title,
                "url": paper.url,
                "content": paper.text or "",
                "original_query": title,
                "cleaned_query": cleaned_title,
                "content_quality": "fallback"
            }
        else:
            return {
                "success": False,
                "title": None,
                "url": None,
                "content": "",
                "original_query": title,
                "cleaned_query": cleaned_title,
                "error": "No results found"
            }
    except Exception as e:
        return {
            "success": False,
            "title": None,
            "url": None,
            "content": "",
            "original_query": title,
            "cleaned_query": cleaned_title,
            "error": str(e)
        }


def call_openai_api(messages, model=None):
    """Call OpenAI API and track token usage"""
    model = model or OPENAI_MODEL
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": model,
        "messages": messages
    }
    
    response = requests.post(
        f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions",
        headers=headers,
        json=data,
        timeout=120
    )
    if MODEL_SLEEP_SECONDS > 0:
        time.sleep(MODEL_SLEEP_SECONDS)
    
    if response.status_code != 200:
        raise Exception(f"API error: {response.status_code} - {sanitize_api_error_text(response.text)}")
    
    result = response.json()
    usage = result.get("usage", {})
    
    return {
        "content": result["choices"][0]["message"]["content"],
        "input_tokens": usage.get("prompt_tokens", 0),
        "output_tokens": usage.get("completion_tokens", 0)
    }


def generate_research_ideas(predecessor_contents, k=10):
    """Generate k research ideas based on predecessor paper contents"""
    
    # Build context from predecessors - only use quality content
    context_parts = []
    for i, pred in enumerate(predecessor_contents):
        if pred.get("success") and pred.get("content"):
            content = pred["content"]
            # Skip if content is too short or low quality
            if len(content) < 300:
                continue
            content = content[:6000]  # Limit each paper's content
            context_parts.append(f"=== Paper {i+1}: {pred.get('title', 'Unknown')} ===\n{content}\n")
    
    if not context_parts:
        return None, 0, 0
    
    context = "\n".join(context_parts)
    
    prompt = f"""You are a research scientist analyzing recent papers to identify promising research directions.

Based on the following papers, generate exactly {k} novel research ideas that could naturally follow from this body of work. Each idea should:
1. Build upon concepts, methods, or findings from these papers
2. Be specific and actionable (not vague)
3. Represent a meaningful contribution to the field

Papers:
{context}

Generate exactly {k} research ideas. For each idea, provide:
- A concise title (1 line)
- A brief description of the key contribution (2-3 sentences)

Format your response as a numbered list (1-{k})."""

    messages = [{"role": "user", "content": prompt}]
    
    result = call_openai_api(messages)
    return result["content"], result["input_tokens"], result["output_tokens"]


def judge_similarity(generated_idea, ground_truth_title, ground_truth_contribution):
    """Use LLM to judge if generated idea matches ground truth"""
    
    prompt = f"""You are evaluating whether a generated research idea matches a real published paper.

Generated Idea:
{generated_idea}

Real Published Paper:
Title: {ground_truth_title}
Contribution: {ground_truth_contribution}

Does the generated idea capture the same core concept, approach, or contribution as the real paper?
Consider semantic similarity, not exact wording. The idea should address the same problem with a similar approach.

Respond with ONLY one of:
- "MATCH" if the generated idea substantially aligns with the real paper's core contribution
- "NO_MATCH" if they are about different topics or approaches"""

    messages = [{"role": "user", "content": prompt}]
    
    result = call_openai_api(messages)
    response = result["content"].strip().upper()
    
    is_match = "MATCH" in response and "NO_MATCH" not in response
    
    return is_match, result["input_tokens"], result["output_tokens"]


def parse_ideas_from_response(response_text):
    """Parse individual ideas from the generated response"""
    ideas = []
    
    # Split by numbered items (1., 2., etc.)
    pattern = r'\d+\.\s*\*?\*?([^*\n]+)\*?\*?\s*\n([^0-9]+?)(?=\d+\.|$)'
    matches = re.findall(pattern, response_text, re.DOTALL)
    
    if matches:
        for title, description in matches:
            ideas.append(f"{title.strip()}\n{description.strip()}")
    else:
        # Fallback: split by double newlines or numbered patterns
        parts = re.split(r'\n\s*\d+[\.\)]\s*', response_text)
        ideas = [p.strip() for p in parts if p.strip() and len(p.strip()) > 20]
    
    return ideas[:10]  # Return at most 10


def load_synthesis_data(data_dir):
    """Load all synthesis JSON files from the data directory"""
    papers = []
    
    synthesis_files = sorted(Path(data_dir).glob("synthesis_*.json"))
    
    for filepath in synthesis_files:
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            # Extract paper info from the new structure
            paper_title = data.get("title", "")
            sg = data.get("synthesis_graph", {})
            contribution = sg.get("target_paper_contribution", "")
            
            # Extract predecessor titles
            predecessors = []
            for pred in sg.get("intellectual_predecessors", []):
                if isinstance(pred, dict):
                    pred_title = pred.get("paper_title", "")
                    if pred_title:
                        predecessors.append(pred_title)
                elif isinstance(pred, str):
                    predecessors.append(pred)
            
            if paper_title and predecessors:
                papers.append({
                    "paper_title": paper_title,
                    "contribution": contribution,
                    "predecessors": predecessors,
                    "source_file": filepath.name
                })
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
    
    return papers


def load_context_cache(cache_path):
    """Load Exa predecessor_details from a Sci-Reasoning result artifact."""
    with open(cache_path, "r") as f:
        data = json.load(f)

    cache = {}
    for record in data.get("results", []):
        title = record.get("paper_title")
        details = record.get("predecessor_details") or []
        if title and details:
            cache[title] = details

    return cache, data.get("summary", {})


def normalize_for_alignment(text):
    """Normalize paper titles for cache-vs-synthesis diagnostic overlap only."""
    text = clean_title_for_search(str(text or ""))
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def cache_query_title(pred):
    """Return the cache-side title/query used for predecessor alignment diagnostics."""
    return pred.get("original_query") or pred.get("title") or ""


def cache_alignment(predecessor_titles, cached_details):
    """Compare current synthesis predecessors against cached predecessor_details."""
    synthesis_norm = {normalize_for_alignment(t): t for t in predecessor_titles if t}
    cache_norm = {
        normalize_for_alignment(cache_query_title(pred)): cache_query_title(pred)
        for pred in cached_details
        if cache_query_title(pred)
    }
    overlap = sorted(set(synthesis_norm) & set(cache_norm))
    synthesis_only = sorted(set(synthesis_norm) - set(cache_norm))
    cache_only = sorted(set(cache_norm) - set(synthesis_norm))
    return {
        "synthesis_predecessor_count": len(predecessor_titles),
        "cached_predecessor_count": len(cached_details),
        "normalized_title_overlap_count": len(overlap),
        "normalized_title_overlap": [synthesis_norm[k] for k in overlap],
        "synthesis_only_predecessors": [synthesis_norm[k] for k in synthesis_only],
        "cache_only_predecessors": [cache_norm[k] for k in cache_only],
    }


def evaluate_single_paper(paper_data, paper_idx, k=10):
    """Evaluate idea generation for a single paper"""
    print(f"\n{'='*70}")
    print(f"[{paper_idx}] Evaluating: {paper_data['paper_title'][:60]}...")
    print(f"    Predecessors: {len(paper_data['predecessors'])}")
    
    # Step 1: Load predecessor papers from cached Exa retrieval results
    predecessor_contents = CONTEXT_CACHE_BY_TITLE.get(paper_data["paper_title"], [])
    alignment = cache_alignment(paper_data["predecessors"], predecessor_contents)
    crawl_successes = 0
    quality_content = 0
    
    print(f"    Loading cached Exa contexts from: {CONTEXT_CACHE_PATH}")
    print(
        "    Cache/synthesis predecessor overlap: "
        f"{alignment['normalized_title_overlap_count']}/"
        f"{alignment['synthesis_predecessor_count']}"
    )

    for i, result in enumerate(predecessor_contents):
        query = cache_query_title(result) or f"Cached predecessor {i+1}"
        print(f"    Cached [{i+1}/{len(predecessor_contents)}]: {query[:50]}...")

        if result["success"]:
            crawl_successes += 1
            content_len = len(result.get("content", ""))
            quality = result.get("content_quality", "unknown")
            if quality in ["good", "good_from_html"]:
                quality_content += 1
            print(f"        ✓ Found: {result.get('url', 'N/A')[:60]} ({content_len} chars, {quality})")
        else:
            print(f"        ✗ Not found: {result.get('error', 'Unknown error')}")
    
    crawl_rate = crawl_successes / len(predecessor_contents) if predecessor_contents else 0
    quality_rate = quality_content / len(predecessor_contents) if predecessor_contents else 0
    print(f"    Cache success: {crawl_successes}/{len(predecessor_contents)} ({crawl_rate*100:.1f}%)")
    print(f"    Quality content: {quality_content}/{len(predecessor_contents)} ({quality_rate*100:.1f}%)")
    
    # Step 2: Generate research ideas
    print(f"    Generating {k} research ideas...")
    
    total_input_tokens = 0
    total_output_tokens = 0
    
    ideas_text, in_tokens, out_tokens = generate_research_ideas(predecessor_contents, k)
    total_input_tokens += in_tokens
    total_output_tokens += out_tokens
    
    if not ideas_text:
        print(f"    ✗ Failed to generate ideas (no quality content crawled)")
        return {
            "paper_idx": paper_idx,
            "paper_title": paper_data["paper_title"],
            "contribution": paper_data["contribution"],
            "num_predecessors": len(paper_data["predecessors"]),
            "predecessors_crawled": crawl_successes,
            "quality_content": quality_content,
            "crawl_rate": crawl_rate,
            "quality_rate": quality_rate,
            "ideas_generated": 0,
            "hit_at_k": False,
            "matching_idea_idx": None,
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "predecessor_details": predecessor_contents,
            "cache_alignment": alignment,
            "generated_ideas": [],
            "judgments": []
        }
    
    # Parse individual ideas
    ideas = parse_ideas_from_response(ideas_text)
    print(f"    Parsed {len(ideas)} ideas")
    
    # Step 3: Judge each idea against ground truth
    print(f"    Judging similarity to ground truth...")
    
    hit = False
    matching_idx = None
    judgments = []
    
    for i, idea in enumerate(ideas):
        is_match, in_tokens, out_tokens = judge_similarity(
            idea, 
            paper_data["paper_title"],
            paper_data["contribution"]
        )
        total_input_tokens += in_tokens
        total_output_tokens += out_tokens
        
        judgments.append({
            "idea_idx": i,
            "idea_text": idea[:200],
            "is_match": is_match
        })
        
        if is_match and not hit:
            hit = True
            matching_idx = i
            print(f"        ✓ HIT at idea {i+1}!")
        
        time.sleep(0.2)  # Rate limiting
    
    if not hit:
        print(f"        ✗ No match found")
    
    return {
        "paper_idx": paper_idx,
        "paper_title": paper_data["paper_title"],
        "contribution": paper_data["contribution"],
        "num_predecessors": len(paper_data["predecessors"]),
        "predecessors_crawled": crawl_successes,
        "quality_content": quality_content,
        "crawl_rate": crawl_rate,
        "quality_rate": quality_rate,
        "ideas_generated": len(ideas),
        "hit_at_k": hit,
        "matching_idea_idx": matching_idx,
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "predecessor_details": predecessor_contents,
        "cache_alignment": alignment,
        "generated_ideas": ideas,
        "generated_ideas_raw": ideas_text,
        "judgments": judgments
    }


def main():
    """Main evaluation pipeline"""
    global EXA_API_KEY, OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL, MODEL_SLEEP_SECONDS, CONTEXT_CACHE_PATH, CONTEXT_CACHE_BY_TITLE, CONTEXT_CACHE_SUMMARY, OUTPUT_PATH, exa
    parser = argparse.ArgumentParser(description="Research Idea Generation Evaluation v4 (Cached Exa Contexts)")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--context-cache", default=str(DEFAULT_CONTEXT_CACHE), help="Sci-Reasoning result JSON containing predecessor_details")
    parser.add_argument("--output", help="Output JSON path")
    parser.add_argument("--smoke", type=int, help="Run only the first N papers")
    parser.add_argument("--dry-run", action="store_true", help="Load data and validate configuration without API calls")
    parser.add_argument("--model", default=None, help="OpenAI-compatible model name; overrides OPENAI_MODEL")
    parser.add_argument("--base-url", dest="base_url", default=None, help="OpenAI-compatible base URL; overrides OPENAI_BASE_URL")
    parser.add_argument("--api-key", dest="api_key", default=None, help="OpenAI-compatible API key; overrides OPENAI_API_KEY")
    parser.add_argument("--exa-api-key", dest="exa_api_key", default=None, help="Exa API key; overrides EXA_API_KEY")
    parser.add_argument("--sleep-seconds", type=float, default=0.0, help="Sleep after each model API call")
    args = parser.parse_args()

    EXA_API_KEY = args.exa_api_key if args.exa_api_key is not None else os.getenv("EXA_API_KEY", "")
    OPENAI_API_KEY = args.api_key if args.api_key is not None else os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL = args.base_url if args.base_url is not None else os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    OPENAI_MODEL = args.model if args.model is not None else os.getenv("OPENAI_MODEL", "")
    MODEL_SLEEP_SECONDS = args.sleep_seconds
    CONTEXT_CACHE_PATH = Path(args.context_cache)
    OUTPUT_PATH = Path(args.output) if args.output else None
    exa = Exa(api_key=EXA_API_KEY) if Exa is not None and EXA_API_KEY else None
    CONTEXT_CACHE_BY_TITLE, CONTEXT_CACHE_SUMMARY = load_context_cache(CONTEXT_CACHE_PATH)

    print("="*70)
    print("Research Idea Generation Evaluation v4 (Cached Exa Contexts)")
    print("="*70)
    print(f"Model: {OPENAI_MODEL}")
    print(f"k: 10")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    # Load data
    data_dir = args.data_dir
    papers = load_synthesis_data(data_dir)
    if args.smoke:
        papers = papers[:args.smoke]
    print(f"\nLoaded {len(papers)} papers from {data_dir}")
    print(f"Loaded cached Exa contexts for {len(CONTEXT_CACHE_BY_TITLE)} targets from {CONTEXT_CACHE_PATH}")

    missing_cache_titles = [paper["paper_title"] for paper in papers if paper["paper_title"] not in CONTEXT_CACHE_BY_TITLE]
    alignment_rows = [
        cache_alignment(paper["predecessors"], CONTEXT_CACHE_BY_TITLE.get(paper["paper_title"], []))
        for paper in papers
    ]
    min_overlap = min((row["normalized_title_overlap_count"] for row in alignment_rows), default=0)
    min_cached = min((row["cached_predecessor_count"] for row in alignment_rows), default=0)
    print(f"Missing cache targets: {len(missing_cache_titles)}")
    print(f"Minimum cached predecessors per target: {min_cached}")
    print(f"Minimum synthesis/cache predecessor title overlap: {min_overlap}")

    if args.dry_run:
        print("Dry run: no model API calls will be made.")
        print(f"OPENAI_API_KEY configured: {bool(OPENAI_API_KEY)}")
        for idx, paper in enumerate(papers[:3]):
            alignment = alignment_rows[idx]
            print(
                f"  [{idx}] {paper['paper_title'][:80]} | "
                f"synthesis_predecessors={len(paper['predecessors'])} | "
                f"cached_predecessors={alignment['cached_predecessor_count']} | "
                f"overlap={alignment['normalized_title_overlap_count']}"
            )
        return 0

    missing = []
    if not OPENAI_API_KEY:
        missing.append("missing_env:OPENAI_API_KEY")
    if not OPENAI_MODEL:
        missing.append("missing_env:OPENAI_MODEL")
    if missing_cache_titles:
        missing.append(f"missing_cache_targets:{len(missing_cache_titles)}")
    if min_cached == 0:
        missing.append("empty_cached_predecessors")
    if missing:
        print("INPUT INVALID:")
        for item in missing:
            print(f"  - {item}")
        return 1
    
    # Run evaluation
    results = []
    total_input_tokens = 0
    total_output_tokens = 0
    
    start_time = time.time()
    
    for idx, paper in enumerate(papers):
        result = evaluate_single_paper(paper, idx, k=10)
        results.append(result)
        
        total_input_tokens += result["input_tokens"]
        total_output_tokens += result["output_tokens"]
        
        # Progress update
        hits_so_far = sum(1 for r in results if r["hit_at_k"])
        print(f"\n    Progress: {idx+1}/{len(papers)} | Hits: {hits_so_far}/{idx+1} ({hits_so_far/(idx+1)*100:.1f}%)")
        
        input_cost = (total_input_tokens / 1_000_000) * INPUT_COST_PER_1M
        output_cost = (total_output_tokens / 1_000_000) * OUTPUT_COST_PER_1M
        print(f"    Tokens: {total_input_tokens:,} in / {total_output_tokens:,} out | Cost: ${input_cost + output_cost:.2f}")
        
        # Save intermediate results every 10 papers
        if (idx + 1) % 10 == 0:
            save_results(results, total_input_tokens, total_output_tokens, start_time, interim=True)
    
    # Final save
    save_results(results, total_input_tokens, total_output_tokens, start_time, interim=False)
    
    # Print summary
    elapsed = time.time() - start_time
    hits = sum(1 for r in results if r["hit_at_k"])
    avg_crawl = sum(r["crawl_rate"] for r in results) / len(results)
    avg_quality = sum(r.get("quality_rate", 0) for r in results) / len(results)
    
    input_cost = (total_input_tokens / 1_000_000) * INPUT_COST_PER_1M
    output_cost = (total_output_tokens / 1_000_000) * OUTPUT_COST_PER_1M
    total_cost = input_cost + output_cost
    
    print("\n" + "="*70)
    print("FINAL RESULTS")
    print("="*70)
    print(f"Papers evaluated: {len(results)}")
    print(f"Hit@10: {hits}/{len(results)} = {hits/len(results)*100:.2f}%")
    print(f"Average crawl rate: {avg_crawl*100:.1f}%")
    print(f"Average quality content rate: {avg_quality*100:.1f}%")
    print(f"Runtime: {elapsed/60:.1f} minutes")
    print(f"\nAPI Cost:")
    print(f"  Input:  {total_input_tokens:,} tokens = ${input_cost:.2f}")
    print(f"  Output: {total_output_tokens:,} tokens = ${output_cost:.2f}")
    print(f"  Total:  ${total_cost:.2f}")
    print("="*70)
    return 0


def save_results(results, total_input_tokens, total_output_tokens, start_time, interim=False):
    """Save results to JSON file"""
    elapsed = time.time() - start_time
    hits = sum(1 for r in results if r["hit_at_k"])
    avg_crawl = sum(r["crawl_rate"] for r in results) / len(results) if results else 0
    avg_quality = sum(r.get("quality_rate", 0) for r in results) / len(results) if results else 0
    alignments = [r.get("cache_alignment", {}) for r in results]
    avg_cached_predecessors = (
        sum(a.get("cached_predecessor_count", 0) for a in alignments) / len(alignments)
        if alignments else 0
    )
    avg_overlap = (
        sum(a.get("normalized_title_overlap_count", 0) for a in alignments) / len(alignments)
        if alignments else 0
    )
    min_overlap = min((a.get("normalized_title_overlap_count", 0) for a in alignments), default=0)
    
    input_cost = (total_input_tokens / 1_000_000) * INPUT_COST_PER_1M
    output_cost = (total_output_tokens / 1_000_000) * OUTPUT_COST_PER_1M
    
    output_data = {
        "summary": {
            "model": OPENAI_MODEL,
            "k": 10,
            "crawl_method": "cached_exa_from_scireasoning_result",
            "cache_source": str(CONTEXT_CACHE_PATH),
            "cache_source_summary": CONTEXT_CACHE_SUMMARY,
            "cache_mode": "target_title_to_predecessor_details",
            "cache_caveat": (
                "Cached predecessor_details are loaded by target title from a Sci-Reasoning result artifact. "
                "They are Exa-retrieved paper contents but may not match the current synthesis predecessor-title list."
            ),
            "total_papers": len(results),
            "hits": hits,
            "hit_rate_percent": round(hits / len(results) * 100, 2) if results else 0,
            "average_crawl_rate": round(avg_crawl * 100, 2),
            "average_quality_rate": round(avg_quality * 100, 2),
            "average_cached_predecessors": round(avg_cached_predecessors, 2),
            "average_synthesis_cache_title_overlap": round(avg_overlap, 2),
            "minimum_synthesis_cache_title_overlap": min_overlap,
            "runtime_minutes": round(elapsed / 60, 2),
            "cost": {
                "input_tokens": total_input_tokens,
                "output_tokens": total_output_tokens,
                "input_cost_usd": round(input_cost, 2),
                "output_cost_usd": round(output_cost, 2),
                "total_cost_usd": round(input_cost + output_cost, 2)
            },
            "timestamp": datetime.now().isoformat()
        },
        "results": results
    }
    
    suffix = "_interim" if interim else "_final"
    if OUTPUT_PATH:
        output_path_obj = OUTPUT_PATH
        if interim:
            output_path_obj = OUTPUT_PATH.with_name(f"{OUTPUT_PATH.stem}_interim{OUTPUT_PATH.suffix}")
    else:
        output_path_obj = Path(f"projects/research_idea_evaluation/results/evaluation_results_cache_exa{suffix}.json")
    
    os.makedirs(output_path_obj.parent, exist_ok=True)
    
    with open(output_path_obj, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\n    Results saved to: {output_path_obj}")


if __name__ == "__main__":
    sys.exit(main())
