import scrapy
import os
import re
from datetime import datetime


def generate_month_list(start_date, end_date):
    """生成从 start_date 到 end_date 的所有 YYMM 组合"""
    months = []
    y, m = start_date.year, start_date.month
    ey, em = end_date.year, end_date.month
    while (y, m) <= (ey, em):
        months.append(f"{y}-{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


class ArxivSpider(scrapy.Spider):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        categories = os.environ.get("CATEGORIES", "cs.CV")
        categories = categories.split(",")
        self.target_categories = set(map(str.strip, categories))

        start_date_str = os.environ.get("START_DATE", "")
        end_date_str = os.environ.get("END_DATE", "")

        if start_date_str:
            start_date = datetime.strptime(start_date_str, "%Y-%m-%d")
            end_date = (
                datetime.strptime(end_date_str, "%Y-%m-%d")
                if end_date_str
                else datetime.now()
            )
            months = generate_month_list(start_date, end_date)
            self.start_urls = [
                f"https://arxiv.org/list/{cat}/{m}"
                for cat in self.target_categories
                for m in months
            ]
        else:
            self.start_urls = [
                f"https://arxiv.org/list/{cat}/new"
                for cat in self.target_categories
            ]

    name = "arxiv"
    allowed_domains = ["arxiv.org"]

    def parse(self, response):
        anchors = []
        for li in response.css("div[id=dlpage] ul li"):
            href = li.css("a::attr(href)").get()
            if href and "item" in href:
                anchors.append(int(href.split("item")[-1]))

        for paper in response.css("dl dt"):
            paper_anchor = paper.css("a[name^='item']::attr(name)").get()
            if not paper_anchor:
                continue

            paper_id = int(paper_anchor.split("item")[-1])
            if anchors and paper_id >= anchors[-1]:
                continue

            abstract_link = paper.css("a[title='Abstract']::attr(href)").get()
            if not abstract_link:
                continue

            arxiv_id = abstract_link.split("/")[-1]

            paper_dd = paper.xpath("following-sibling::dd[1]")
            if not paper_dd:
                continue

            subjects_text = paper_dd.css(".list-subjects .primary-subject::text").get()
            if not subjects_text:
                subjects_text = paper_dd.css(".list-subjects::text").get()

            if subjects_text:
                categories_in_paper = re.findall(r'\(([^)]+)\)', subjects_text)
                paper_categories = set(categories_in_paper)
                if paper_categories.intersection(self.target_categories):
                    yield {
                        "id": arxiv_id,
                        "categories": list(paper_categories),
                    }
                    self.logger.info(f"Found paper {arxiv_id} with categories {paper_categories}")
                else:
                    self.logger.debug(f"Skipped paper {arxiv_id} with categories {paper_categories} (not in target {self.target_categories})")
            else:
                self.logger.warning(f"Could not extract categories for paper {arxiv_id}, including anyway")
                yield {
                    "id": arxiv_id,
                    "categories": [],
                }
