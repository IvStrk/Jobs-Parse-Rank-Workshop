import bs4
import json
import openai
import os
from pprint import pprint
import random
import requests
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from tqdm import tqdm


CAREER_WEBSITES = [
    {
        # set a correct url
        "url": "https://zzz.com/careers/search",
        "element_wait_xpath": None,
        "pagination": None,
    },
    {
        # set a correct url_template
        "url_template": "https://yyy.com/en/search?offset={offset}&result_limit=10&sort=relevant&distanceType=Mi&radius=24km&latitude=&longitude=&loc_group_id=&loc_query=California%2C%20United%20States&base_query=machine%20learning&city=&country=USA&region=California&county=&query_options=&",
        "element_wait_xpath": '//h3[@class="job-title"]',
        "pagination": {
            "type": "offset",
            "start": 0,
            "step": 10,
        },
    },
]

CANDIDATE_BACKGROUND = """I'm a ML engineer with 8 years of experience in this field, specifically with classical ML, recommender systems and NLP tasks. Had several years of experience leading Data Science teams."""

CANDIDATE_JOB_REQUIREMENTS = """I'm looking for a senior ML engineer or ML engineering manager position."""

JOB_DESCRIPTIONS_TO_SCORE_MAX = 20


def page_source_code_get(url):
    """Get page source code from url."""
    r = requests.get(url)
    return r.content

def page_source_code_selenium_get(url, driver, element_wait_xpath):
    """Get page source code from url using selenium."""
    driver.get(url)
    wait = WebDriverWait(driver, 5)
    if element_wait_xpath:
        try:
            _ = wait.until(EC.presence_of_element_located((By.XPATH, element_wait_xpath)))
        except TimeoutException:
            return None

    page_source_code = driver.page_source

    return page_source_code

def url_domain_get(url):
    """Get domain from url."""
    return url.split("/")[2]

def url_base_get(url):
    """Get base from url."""
    return url.split("/")[0] + "//" + url.split("/")[2]

def html_hyperlinks_extract(page_source_code):
    """Extract hyperlinks and their text from page source code."""
    soup = bs4.BeautifulSoup(page_source_code, "html.parser")
    hyperlinks = soup.find_all("a")

    hyperlinks_data = [
        {
            "text_full": link.get_text(separator=" ", strip=True),
            "text_first": link.get_text(separator="\n", strip=True).split("\n")[0],
            "href": link.get("href")
        }
        for link in hyperlinks
        if link.get("href") is not None and (link.get("href").startswith("http") or link.get("href").startswith("/"))
    ]

    return hyperlinks_data

def hyperlinks_enrich(hyperlinks_data, url):
    """Enrich hyperlinks data."""
    domain = url_domain_get(url)
    base = url_base_get(url)

    for link in hyperlinks_data:
        # add absolute link
        if link["href"].startswith("/"):
            link["url"] = base + link["href"]
        else:
            link["url"] = link["href"]
        
        # check if url domain is the same as the page domain
        if url_domain_get(link["url"]) == domain:
            link["is_internal"] = True
        else:
            link["is_internal"] = False

    return hyperlinks_data

def career_page_next_get(career_page, page_number):
    """Get the next page (url and other metadata)"""
    if career_page["pagination"] is None and page_number == 1:
        return career_page
    elif career_page["pagination"] is None and page_number > 1:
        return None
    
    if career_page["pagination"]["type"] == "offset":
        career_page_next = career_page.copy()
        offset_curr = career_page["pagination"]["start"] + (page_number - 1) * career_page["pagination"]["step"]
        career_page_next["url"] = career_page_next["url_template"].format(offset=offset_curr)
        return career_page_next
    else:
        raise NotImplementedError(f'Pagination type {career_page["pagination"]["type"]} is not implemented')

def career_page_parse(career_page, driver):
    """Parse one career page"""
    page_source_code = page_source_code_selenium_get(career_page["url"], driver, career_page["element_wait_xpath"])
    if page_source_code is None:
        return None
    
    page_hyperlinks = html_hyperlinks_extract(page_source_code)
    page_hyperlinks = hyperlinks_enrich(page_hyperlinks, career_page["url"])

    return page_hyperlinks

def career_website_parse(career_website, driver):
    """Parse one career website"""
    hyperlinks = []
    page_number = 1
    career_page = career_page_next_get(career_website, page_number)
    while career_page is not None:
        hyperlinks_curr = career_page_parse(career_page, driver)
        if hyperlinks_curr is None:
            break
        hyperlinks.extend(hyperlinks_curr)
        career_page = career_page_next_get(career_page, page_number)
        page_number +=1 

    return hyperlinks

def career_websites_parse():
    """Parse career websites"""
    options = Options()
    options.add_argument("--headless")
    with webdriver.Chrome(options=options) as driver:
        hyperlinks = []
        for career_website in CAREER_WEBSITES:
            hyperlinks_curr = career_website_parse(career_website, driver)
            hyperlinks.extend(hyperlinks_curr)

    return hyperlinks

def openai_key_load():
    """Read key from ~/.openai/key.txt and save it to OPENAI_API_KEY enviroment variable"""
    environ_key = "OPENAI_API_KEY"
    if environ_key not in os.environ:
        path = os.path.join(os.path.expanduser("~"), ".openai", "key.txt")
        try:
            with open(path, "r") as f:
                openai_key = f.read().strip()
        except FileNotFoundError:
            raise FileNotFoundError(f"OpenAI key file not found at {path}")
        os.environ[environ_key] = openai_key

    return os.environ[environ_key]

def openai_chat_completion_request(prompt):
    """Send request to OpenAI chatGPT API to complete prompt"""
    openai.api_key = openai_key_load()

    chat_completion = openai.ChatCompletion.create(
        model="gpt-3.5-turbo", 
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
    )

    return chat_completion.choices[0].message.content

def job_titles_filter_prompt_compile(hyperlink_texts, job_requirements):
    """Compile prompt for job titles filter"""
    hyperlink_texts_str = '\n'.join(hyperlink_texts)
    prompt = (
        f"{job_requirements}\n\n"
        f"I parsed a career website and found the following hyperlink texts:\n"
        f"{hyperlink_texts_str}\n\n"
        f"Some of the texts are jobs titles while others are just regular website links.\n"
        f"Please identify the jobs titles from the texts above which can be relevant to me.\n"
        f"Provide output as a JSON with the only key `job_titles` which contains a list of relevant job titles."
    )
    return prompt

def job_titles_filter(hyperlinks, job_requirements):
    """Filter job titles from hyperlink texts using GPT"""
    hyperlink_texts = set([link["text_first"] for link in hyperlinks])
    prompt = job_titles_filter_prompt_compile(hyperlink_texts, job_requirements)
    job_titles_text = openai_chat_completion_request(prompt)
    job_titles = json.loads(job_titles_text)['job_titles']

    print("\n=== Relevant job titles:\n", job_titles)
    print("\n=== Irrelevant hyperlink texts:\n", set(hyperlink_texts) - set(job_titles))
    print("\n=== Wrong LLM output:\n", set(job_titles) - set(hyperlink_texts))

    assert len(set(job_titles) - set(hyperlink_texts)) == 0, "LLM output contains job titles which are not in the hyperlink texts"

    return job_titles

def html_visible_text_get(html):
    """Get visible text from HTML"""
    soup = bs4.BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator="\n")
    return text

def job_descriptions_parse(hyperlinks, job_titles):
    """Parse job descriptions based on the relevant job titles"""
    job_titles = set(job_titles)
    urls_relevant = [link["url"] for link in hyperlinks if link["text_first"] in job_titles]

    parsed_job_descriptions = []

    options = Options()
    options.add_argument("--headless")
    with webdriver.Chrome(options=options) as driver:
        for url in tqdm(urls_relevant):
            page_source_code = page_source_code_selenium_get(url, driver, element_wait_xpath=None)
            parsed_job_descriptions.append(
                {
                    "url": url,
                    "page_text": html_visible_text_get(page_source_code),
                }
            )

    return parsed_job_descriptions

def job_description_relevance_prompt_get(candidate_background, candidate_job_requirements, page_text):
    """Compile prompt for job description relevance scoring"""
    prompt = (
        f"{candidate_background}\n\n"
        f"{candidate_job_requirements}\n\n"
        f"I parsed a website with a job description. Here is all the visible text from the page:\n"
        f"===\n{page_text}\n===\n\n"
        f"Please identify how relevant this position is to my requirements and background.\n"
        f"Provide a score between 0 and 10 where 0 is for position which is not even from my field, 1 for position from my field but not relevant to me, and 10 for position which is a perfect match to me.\n"
        f"Output results as a JSON with the following keys:\n"
        f"- `title` - the job title from the page;\n"
        f"- `explanation` - explanation of how the position is relevant (or not relevant) to me;\n"
        f"- `score` - score between 0 and 10.\n"
    )
    return prompt

def job_relevance_llm_score(job_descriptions):
    """Get job relevance score from LLM"""
    job_relevance_scores = []
    random.shuffle(job_descriptions)
    for job_description in tqdm(job_descriptions[:JOB_DESCRIPTIONS_TO_SCORE_MAX]):
        prompt = job_description_relevance_prompt_get(CANDIDATE_BACKGROUND, CANDIDATE_JOB_REQUIREMENTS, job_description["page_text"])
        llm_output = openai_chat_completion_request(prompt)
        job_relevance_score = json.loads(llm_output)
        job_relevance_score["url"] = job_description["url"]
        job_relevance_scores.append(job_relevance_score)

    return job_relevance_scores

def main():
    hyperlinks = career_websites_parse()
    job_titles_relevant = job_titles_filter(hyperlinks, CANDIDATE_JOB_REQUIREMENTS)
    job_descriptions = job_descriptions_parse(hyperlinks, job_titles_relevant)
    job_relevance_scores = job_relevance_llm_score(job_descriptions)

    pprint(sorted(job_relevance_scores, key=lambda x: x["score"], reverse=True))

if __name__ == "__main__":
    main()
