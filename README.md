# Scraping and Ranking with GPT Workshop
Code for the the [Scraping and Ranking with GPT workshop](https://www.codementor.io/events/automate-your-job-search-scraping-and-ranking-with-gpt-hciurs5ewe).

The code scrapes and ranks job descriptions according to the candidate background.
## Before starting to use the code
- Put your OpenAI API key in the `~/.openai/key.txt` file or assign it to the `OPENAI_API_KEY` environmental variable;
- Check the values of the global variables in the code: `CAREER_WEBSITES`, `CANDIDATE_BACKGROUND`, `CANDIDATE_JOB_REQUIREMENTS`;
- The code was tested on python 3.11 (if you have a lower python version you can start with removing library versions in `requirements.txt`);
- Create and activate virtual envrironment: `virtualenv venv && source venv/bin/activate`;
- Install libraries: `pip install -r requirements.txt`;
- Make sure that the legal side of your scraping project is covered.
## Using the code
Just execute `python jobs_parse_rank/main.py`.
## Further improvements
Thy this if you want to play with the code further:
- [ ] Extract more information from the job description: salary range, benefits, location, etc;
- [ ] Request multiple scores: background to position fit, requirements to position fit, location fit;
- [ ] Calculate the cost of GPT usage;
- [ ] Test the code on the other career pages and make it work for the pages where it doesn't [HARD];
- [ ] Improve the wording in the scoring prompt to make the results better [HARD].


