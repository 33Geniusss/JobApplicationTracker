"""Development helper: rebuild the bundled candidate list (requires beautifulsoup4).
The application itself never downloads a directory or uses this dependency.
"""
import json
from pathlib import Path
import urllib.request
import sys
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from localization import bilingual_catalog

GROUPS = {
    "AI / Machine Learning": "OpenAI|Anthropic|xAI|Perplexity|Hugging Face|Scale AI|Together AI|Anyscale|Databricks|DataRobot|H2O.ai|C3 AI|SambaNova Systems|Cerebras Systems|Groq|Fireworks AI|Lambda|CoreWeave|Modal|Baseten|Replicate|Runway|Midjourney|Pika|Luma AI|Character.AI|Jasper|Writer|Glean|Hebbia|Harvey|Sierra|Decagon|Cognition|Anysphere|Replit|Codeium / Windsurf|Sourcegraph|Poolside|Magic|Imbue|Thinking Machines Lab|Safe Superintelligence|World Labs|Physical Intelligence|Skild AI|Adept|Snorkel AI|Labelbox|Arize AI|Fiddler AI|Arthur AI|WhyLabs|Weights & Biases|LangChain|LlamaIndex|Unstructured|Cleanlab|Humanloop|Galileo|Patronus AI|Braintrust|Vellum|Dust|Relevance AI|Cartesia|Deepgram|AssemblyAI|Speechmatics|PlayHT|Suno|Riffusion|Descript|Otter.ai|Twelve Labs|Landing AI|Roboflow|Clarifai|Voxel|Encord|Predibase|Lepton AI|Sakana AI",
    "软件 / 云计算": "Microsoft|Google|Amazon|Meta|Apple|Oracle|IBM|Salesforce|Adobe|ServiceNow|Workday|Intuit|Autodesk|Snowflake|Palantir|Datadog|Cloudflare|MongoDB|Confluent|Elastic|Redis|Cockroach Labs|SingleStore|ClickHouse|Starburst|dbt Labs|Fivetran|Airbyte|Astronomer|MotherDuck|Neon|Supabase|Vercel|Netlify|Render|Fly.io|Railway|Docker|GitHub|GitLab|HashiCorp|Postman|Retool|Zapier|Airtable|Notion|Figma|Canva|Miro|Asana|Monday.com|Atlassian|Dropbox|Box|Zoom|Twilio|HubSpot|Amplitude|Mixpanel|Segment|LaunchDarkly|Sentry|Grafana Labs|Temporal|Prefect|Dagster Labs|Pulumi|Harness|JFrog|DigitalOcean|Akamai|Fastly|Aiven",
    "芯片 / 计算机硬件": "NVIDIA|AMD|Intel|Qualcomm|Broadcom|Marvell|Micron Technology|Texas Instruments|Analog Devices|Microchip Technology|Lattice Semiconductor|Synopsys|Cadence Design Systems|Arm|SiFive|Tenstorrent|d-Matrix|Etched|Lightmatter|Lightelligence|Ayar Labs|Celestial AI|Astera Labs|Sambanova|Dell Technologies|HP|Hewlett Packard Enterprise|Supermicro|Cisco|Arista Networks|Juniper Networks|Pure Storage|NetApp|Western Digital|Seagate|Applied Materials|Lam Research|KLA",
    "机器人 / 自动驾驶": "Tesla|Waymo|Zoox|Aurora|Nuro|Applied Intuition|Waabi|Torc Robotics|May Mobility|Plus|Gatik|Kodiak Robotics|Serve Robotics|Starship Technologies|Coco Robotics|Boston Dynamics|Agility Robotics|Figure AI|Apptronik|1X Technologies|Sanctuary AI|Skydio|Zipline|Anduril|Shield AI|Saronic|Saildrone|Gecko Robotics|Dexterity|Covariant|Intrinsic|Symbotic|Locus Robotics|Berkshire Grey|Boston Engineering|Realtime Robotics|Pickle Robot|Standard Bots|Collaborative Robotics|Diligent Robotics|Burro|Carbon Robotics|FarmWise|Built Robotics|Dusty Robotics|Teleo|Outrider|Reliable Robotics|Vention|Path Robotics",
    "互联网 / 金融科技 / 安全": "Netflix|Uber|Lyft|Airbnb|DoorDash|Instacart|Pinterest|Snap|Reddit|Roblox|Discord|Spotify|Duolingo|Yelp|Redfin|Zillow|Expedia Group|Booking Holdings|eBay|Etsy|Chewy|Stripe|Block|PayPal|Affirm|Plaid|Ramp|Brex|Chime|SoFi|Robinhood|Coinbase|Rippling|Gusto|Deel|Ripcord|CrowdStrike|Palo Alto Networks|Zscaler|Okta|SentinelOne|Wiz|Snyk|SailPoint|Tanium|Abnormal AI|Netskope|Fortinet|Rubrik|Cohesity|Vanta|Drata|Verkada|Samsara|Motive|Flock Safety",
}
# Non-US headquartered companies are excluded from this US-focused starter list.
EXCLUDE = {"Sakana AI", "Relevance AI", "Speechmatics", "Canva", "Miro", "Monday.com", "Atlassian", "Aiven", "Arm", "Tenstorrent", "Waabi", "Sanctuary AI", "Vention", "Spotify", "Sambanova"}
ALIASES = {
    "NVIDIA": ["英伟达", "Nvidia Corporation"], "Google": ["谷歌", "Alphabet"],
    "Microsoft": ["微软", "MSFT"], "Amazon": ["亚马逊", "AWS"],
    "Meta": ["Facebook", "脸书"], "Apple": ["苹果"], "Tesla": ["特斯拉"],
    "AMD": ["Advanced Micro Devices", "超威"], "Intel": ["英特尔"],
    "Qualcomm": ["高通"], "IBM": ["International Business Machines"],
    "Oracle": ["甲骨文"], "Cisco": ["思科"], "Dell Technologies": ["Dell", "戴尔"],
    "HP": ["惠普"], "Hewlett Packard Enterprise": ["HPE"],
    "OpenAI": ["Open AI"], "Hugging Face": ["HuggingFace"],
    "Anysphere": ["Cursor"], "Codeium / Windsurf": ["Codeium", "Windsurf"],
    "Boston Dynamics": ["波士顿动力"], "Figure AI": ["Figure"],
    "Weights & Biases": ["WandB", "W&B"], "SambaNova Systems": ["SambaNova"],
    "Micron Technology": ["Micron", "美光"], "Broadcom": ["博通"],
    "Texas Instruments": ["TI", "德州仪器"], "Supermicro": ["Super Micro", "超微"],
    "Block": ["Square"], "Abnormal AI": ["Abnormal Security"],
}


def main():
    records = []
    for category, names in GROUPS.items():
        for name in names.split("|"):
            if name in EXCLUDE:
                continue
            records.append({"name": name, "category": category, "aliases": ALIASES.get(name, []), "source": "", "provenance": "人工整理的候选名称；未逐一核验当前经营、独立法人或招聘状态"})
    # Small early-stage US companies, using names + location from YC's official directory.
    url = "https://www.ycombinator.com/companies/industry/machine-learning"
    soup = BeautifulSoup(urllib.request.urlopen(url, timeout=30).read(), "html.parser")
    known = {r["name"].casefold() for r in records}
    additions = 0
    for a in soup.select("a.justify-start"):
        name_tag = a.select_one("span.text-2xl")
        if not name_tag:
            continue
        name = name_tag.get_text(strip=True)
        metadata = [span.get_text(" ", strip=True) for span in a.select("span.text-gray-700")]
        location = metadata[-1] if metadata else ""
        if not any(city in location for city in ("USA", "San Francisco", "New York", "Boston", "Seattle", "Los Angeles", "Palo Alto", "Mountain View", "San Jose")):
            continue
        if name.casefold() in known:
            continue
        records.append({"name": name, "category": "AI / Machine Learning", "aliases": [], "source": "https://www.ycombinator.com" + a["href"], "provenance": "YC Machine Learning 目录", "location": location})
        known.add(name.casefold())
        additions += 1
        if additions == 25:
            break
    # Keep a practical starter set of 300, with all five categories represented.
    while len(records) > 300:
        candidates = [i for i, r in enumerate(records) if not r["source"] and not r["aliases"] and r["category"] == "软件 / 云计算"]
        records.pop(candidates[-1])
    output = {"version": 1, "curated_date": "2026-10-03", "scope": "美国科技求职公司/招聘品牌候选名单；含子公司及被收购品牌，不保证全部独立存续或正在招聘。", "sources": [url, "https://www.nasdaq.com/NDXT"], "companies": sorted(records, key=lambda r: r["name"].casefold())}
    target = Path(__file__).resolve().parents[1] / "companies.json"
    target.write_text(json.dumps(bilingual_catalog(output), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(records)} companies, including {additions} YC US startup entries.")


if __name__ == "__main__":
    main()
