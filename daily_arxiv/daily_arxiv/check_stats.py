#!/usr/bin/env python3
"""
检查Scrapy爬取统计信息的脚本 / Script to check Scrapy crawling statistics
用于获取去重检查的状态结果 / Used to get deduplication check status results

功能说明 / Features:
- 检查当日与昨日论文数据的重复情况 / Check duplication between today's and yesterday's paper data
- 删除重复论文条目，保留新内容 / Remove duplicate papers, keep new content
- 根据去重后的结果决定工作流是否继续 / Decide workflow continuation based on deduplication results
"""
import json
import sys
import os
import argparse
from datetime import datetime, timedelta

def load_papers_data(file_path):
    """
    从jsonl文件中加载完整的论文数据
    Load complete paper data from jsonl file
    
    Args:
        file_path (str): JSONL文件路径 / JSONL file path
        
    Returns:
        list: 论文数据列表 / List of paper data
        set: 论文ID集合 / Set of paper IDs
    """
    if not os.path.exists(file_path):
        return [], set()
    
    papers = []
    ids = set()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    data = json.loads(line)
                    papers.append(data)
                    ids.add(data.get('id', ''))
        return papers, ids
    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)
        return [], set()

def save_papers_data(papers, file_path):
    """
    保存论文数据到jsonl文件
    Save paper data to jsonl file
    
    Args:
        papers (list): 论文数据列表 / List of paper data
        file_path (str): 文件路径 / File path
    """
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            for paper in papers:
                f.write(json.dumps(paper, ensure_ascii=False) + '\n')
        return True
    except Exception as e:
        print(f"Error saving {file_path}: {e}", file=sys.stderr)
        return False

def perform_deduplication(target_file):
    """
    执行多日去重：删除与历史多日重复的论文条目，保留新内容
    Perform deduplication over multiple past days

    Args:
        target_file (str): 要检查的 JSONL 文件路径 / Path to the JSONL file to check

    Returns:
        str: 去重状态 / Deduplication status
    """

    if not os.path.exists(target_file):
        print(f"数据文件不存在: {target_file} / Data file does not exist", file=sys.stderr)
        return "no_data"

    try:
        today_papers, today_ids = load_papers_data(target_file)
        print(f"目标论文总数: {len(today_papers)} / Target total papers: {len(today_papers)}", file=sys.stderr)

        if not today_papers:
            return "no_data"

        # 收集历史多日 ID 集合 (从 data 目录下所有其他 jsonl 文件收集)
        history_ids = set()
        data_dir = os.path.dirname(target_file) or "../data"
        target_basename = os.path.basename(target_file)
        history_days = 7

        for i in range(1, history_days + 1):
            date_str = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            history_file = os.path.join(data_dir, f"{date_str}.jsonl")
            _, past_ids = load_papers_data(history_file)
            history_ids.update(past_ids)

        # 也检查同目录下其他历史文件 (避免和当前文件自己比较)
        if os.path.isdir(data_dir):
            for fname in os.listdir(data_dir):
                if fname.endswith('.jsonl') and fname != target_basename:
                    fpath = os.path.join(data_dir, fname)
                    _, past_ids = load_papers_data(fpath)
                    history_ids.update(past_ids)

        print(f"历史去重库大小: {len(history_ids)} / History deduplication library size: {len(history_ids)}", file=sys.stderr)

        duplicate_ids = today_ids & history_ids

        if duplicate_ids:
            print(f"发现 {len(duplicate_ids)} 篇历史重复论文 / Found {len(duplicate_ids)} historical duplicate papers", file=sys.stderr)
            new_papers = [paper for paper in today_papers if paper.get('id', '') not in duplicate_ids]

            print(f"去重后剩余论文数: {len(new_papers)} / Remaining papers after deduplication: {len(new_papers)}", file=sys.stderr)

            if new_papers:
                if save_papers_data(new_papers, target_file):
                    print(f"已更新文件，移除 {len(duplicate_ids)} 篇重复论文 / File updated, removed {len(duplicate_ids)} duplicate papers", file=sys.stderr)
                    return "has_new_content"
                else:
                    print("保存去重后的数据失败 / Failed to save deduplicated data", file=sys.stderr)
                    return "error"
            else:
                try:
                    os.remove(target_file)
                    print("所有论文均为重复内容，已删除文件 / All papers are duplicate content, file deleted", file=sys.stderr)
                except Exception as e:
                    print(f"删除文件失败: {e} / Failed to delete file: {e}", file=sys.stderr)
                return "no_new_content"
        else:
            print("所有内容均为新内容 / All content is new", file=sys.stderr)
            return "has_new_content"

    except Exception as e:
        print(f"去重处理失败: {e} / Deduplication processing failed: {e}", file=sys.stderr)
        return "error"

def main():
    """
    检查去重状态并返回相应的退出码
    Check deduplication status and return corresponding exit code

    退出码含义 / Exit code meanings:
    0: 有新内容，继续处理 / Has new content, continue processing
    1: 无新内容，停止工作流 / No new content, stop workflow
    2: 处理错误 / Processing error
    """

    parser = argparse.ArgumentParser(description="去重检查 / Deduplication check")
    parser.add_argument("--file", type=str, default=None,
                        help="要检查的 JSONL 文件路径 / Path to JSONL file to check")
    args = parser.parse_args()

    if args.file:
        target_file = args.file
    else:
        target_file = f"../data/{datetime.now().strftime('%Y-%m-%d')}.jsonl"

    print(f"正在检查文件: {target_file} / Checking file: {target_file}", file=sys.stderr)
    print("正在执行去重检查... / Performing intelligent deduplication check...", file=sys.stderr)

    dedup_status = perform_deduplication(target_file)

    if dedup_status == "has_new_content":
        print("✅ 去重完成，发现新内容，继续工作流 / Deduplication completed, new content found, continue workflow", file=sys.stderr)
        sys.exit(0)
    elif dedup_status == "no_new_content":
        print("⏹️ 去重完成，无新内容，停止工作流 / Deduplication completed, no new content, stop workflow", file=sys.stderr)
        sys.exit(1)
    elif dedup_status == "no_data":
        print("⏹️ 无数据，停止工作流 / No data, stop workflow", file=sys.stderr)
        sys.exit(1)
    elif dedup_status == "error":
        print("❌ 去重处理出错，停止工作流 / Deduplication processing error, stop workflow", file=sys.stderr)
        sys.exit(2)
    else:
        print("❌ 未知去重状态，停止工作流 / Unknown deduplication status, stop workflow", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main() 