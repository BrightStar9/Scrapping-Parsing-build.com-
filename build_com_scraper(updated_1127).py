import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options


# Logging configuration
logging.basicConfig(filename='scraping.log', level=logging.INFO,
                    format='%(asctime)s:%(levelname)s:%(message)s')

# Configuration
INPUT_CSV = "11232024_inventoryfeed.csv"  # Input file path
OUTPUT_CSV = "updated_products.csv"  # Output file path

BASE_URL = "https://www.build.com"

IMAGE_SELECTOR = "div.react-transform-component.transform-component-module_content__FBWxo"  # CSS selector for the clickable image
MODAL_SELECTOR = "div.lh-copy.bg-theme-white.h-100.pa4"  # CSS selector for the modal

def initialize_webdriver():
    """Initialize a Selenium WebDriver with headless mode."""
    options = Options()
    options.add_argument("--headless")  # Run in headless mode
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-extensions")
    options.add_argument("--force-device-scale-factor=1")
    options.add_argument("--enable-features=NetworkService,NetworkServiceInProcess")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")

    prefs = {"profile.managed_default_content_settings.images": 1}
    options.add_experimental_option("prefs", prefs)

    options.add_argument("--window-size=1920*1080")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome()
    return driver

def search_product(model):
    """
    Searches for the product on build.com using the model number.
    Returns the link to the first product's detailed page or None if not found.
    """
    search_url = f"{BASE_URL}/search?term={model}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/58.0.3029.110 Safari/537.3"
    }

    try:
        response = requests.get(search_url, headers=headers)
        if response.status_code != 200:
            logging.error(f"Failed to retrieve search page for model {model}. HTTP Status Code: {response.status_code}")
            return None
        soup = BeautifulSoup(response.content, "html.parser")
        # Find the link to the first product
        product_link_tag = soup.find("a", class_="f-inherit fw-inherit link theme-primary db center mw5", href=True)  # Adjust the class to match actual structure
        if product_link_tag and product_link_tag.get("href"):
            product_link = product_link_tag["href"]
            return f"{BASE_URL}{product_link}"  # Build the full URL
        else:
            logging.warning(f"No product link found for model {model}.")
            return None

    except Exception as e:
        logging.error(f"Error during search for model {model}: {e}")
        return None

def extract_product_details(driver, product_url):
    """
    Extracts product details from the detailed product page.
    Returns a dictionary with the required data or default values if not found.
    """
    product_data = {
        "Classification":"N/A",
        "Name": "N/A",
        "Image_URL": "N/A",
        "Finish": "N/A",
        "Categories": "N/A",
        "Manufacturer_Resources": "N/A",
        "Dimensions&Measurements": "N/A",
        "Included_components": "N/A",
        "Characteristics&Features": "N/A",
        "Warranty&Product_Information": "N/A",
        "Features": "N/A",
        "Electrical&Operational_Information": "N/A",
        "Specifications": "N/A",
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/58.0.3029.110 Safari/537.3"
    }

    try:
        
        response = requests.get(product_url, headers=headers)
        # Extract manufacturer resources (PDF links and names)
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Find all `li` tags
        classification_tag = soup.find("section", class_="dn flex-ns pb3")
        li_tags = classification_tag.find_all("li")
        # Extract text from all `span` tags within `li` tags
        classification_texts = []
        for li in li_tags:
            spans = li.find_all("span")
            for span in spans:
                if span.text.strip():  # Only include non-empty text
                    classification_texts.append(span.text.strip())

        product_data["Classification"] = classification_texts
        # Find the span tag with the specific class
        name_tag = soup.find('span', class_='fw2 di-ns')

        # Extract the text
        if name_tag:
            name = name_tag.get_text(strip=True)  # Use `strip=True` to remove extra whitespace
            product_data["Name"] = name
            
        
        # Find the span with the specific 'data-automation' attribute
        finish_name_tag = soup.find("span", {"data-automation": "finish-name"})
        finish = ""
        # Extract the text if the tag exists
        if finish_name_tag:
            finish_name = finish_name_tag.get_text(strip=True)  # Get the text and strip extra spaces
            finish = finish_name

        # stock_tag = soup.find("span", class_="theme-grey-darker lh-solid")
        # # Extract the text if the tag exists
        # if stock_tag:
        #     stock = stock_tag.get_text(strip=True)  # Get the text and strip extra spaces
        #     finish += "-" + stock 
        product_data["Finish"] = finish

        manufacturer_section = soup.find("h3", string="Manufacturer Resources")

        if manufacturer_section:
            resources_div = manufacturer_section.find_parent("div")
            if resources_div:
                pdf_links = []
                for link_tag in resources_div.find_all("a", href=True):
                    pdf_name = link_tag.find("span").get_text(strip=True) if link_tag.find("span") else "Unknown"
                    pdf_url = link_tag["href"]
                    if pdf_url.startswith("//"):
                        pdf_url = "https:" + pdf_url
                    pdf_links.append(f"{pdf_name}: {pdf_url}")
                product_data["Manufacturer_Resources"] = "; ".join(pdf_links)

        # Extract Dimensions and Measurements
        dimensions_heading = soup.find("h3", string="Dimensions and Measurements")
        if dimensions_heading:
            dimensions_table = dimensions_heading.find_next("table")
            if dimensions_table:
                dimensions_data = []
                rows = dimensions_table.find_all("tr")
                for row in rows:
                    key_tag = row.find("td", class_="w-50").find("span")
                    key = key_tag.get_text(strip=True) if key_tag else "Unknown"
                    value_tag = row.find_all("td")[1]
                    value = value_tag.get_text(strip=True) if value_tag else "N/A"
                    dimensions_data.append(f"{key}: {value}")
                product_data["Dimensions&Measurements"] = "; ".join(dimensions_data)

        # Extract Included Components
        components_heading = soup.find("h3", string="Included Components")
        if components_heading:
            components_table = components_heading.find_next("table")
            if components_table:
                included_components = []
                rows = components_table.find_all("tr")
                for row in rows:
                    key_tag = row.find("td", class_="w-50").find("span")
                    key = key_tag.get_text(strip=True) if key_tag else "Unknown"
                    value_tag = row.find_all("td")[1]
                    value = value_tag.get_text(strip=True) if value_tag else "N/A"
                    included_components.append(f"{key}: {value}")
                product_data["Included_components"] = "; ".join(included_components)

        # Extract Characteristics and Features
        features_heading = soup.find("h3", string="Characteristics and Features")
        if features_heading:
            characteristics = []
            features_table = features_heading.find_next("table")
            if features_table:
                rows = features_table.find_all("tr")
                for row in rows:
                    key_tag = row.find("td", class_="w-50").find("span")
                    key = key_tag.get_text(strip=True) if key_tag else "Unknown"
                    value_tag = row.find_all("td")[1]
                    value = value_tag.get_text(strip=True) if value_tag else "N/A"
                    characteristics.append(f"{key}: {value}")
                product_data["Characteristics&Features"] = "; ".join(characteristics)


        # Extract Electrical and Operational Information
        electric_heading = soup.find("h3", string="Electrical and Operational Information")
        if electric_heading:
            electrical_info = []
            electric_table = electric_heading.find_next("table")
            if electric_table:
                rows = electric_table.find_all("tr")
                for row in rows:
                    key_tag = row.find("td", class_="w-50").find("span")
                    key = key_tag.get_text(strip=True) if key_tag else "Unknown"
                    value_tag = row.find_all("td")[1]
                    value = value_tag.get_text(strip=True) if value_tag else "N/A"
                    electrical_info.append(f"{key}: {value}")
                product_data["Electrical&Operational_Information"] = "; ".join(electrical_info)

        # Extract Warranty and Product Information
        warranty_heading = soup.find("h3", string="Warranty and Product Information")
        if warranty_heading:
            warranty_table = warranty_heading.find_next("table")
            if warranty_table:
                warranty_info = []
                rows = warranty_table.find_all("tr")
                for row in rows:
                    key_tag = row.find("td", class_="w-50").find("span")
                    key = key_tag.get_text(strip=True) if key_tag else "Unknown"
                    value_tag = row.find_all("td")[1]
                    value = value_tag.get_text(strip=True) if value_tag else "N/A"
                    warranty_info.append(f"{key}: {value}")
                product_data["Warranty&Product_Information"] = "; ".join(warranty_info)

        # Extract Features
        features_heading = soup.find("p", string=lambda text: text and "Features:" in text)
        if features_heading:
            features_list = features_heading.find_next("ul")
            if features_list:
                features = []
                li_tags = features_list.find_all("li")
                for li in li_tags:
                    feature = li.get_text(strip=True)
                    features.append(feature)
                product_data["Features"] = features

        # Extract Specifications
        specifications_heading = soup.find("p", string=lambda text: text and "Specifications:" in text)
        if specifications_heading:
            specifications_list = specifications_heading.find_next("ul")
            if specifications_list:
                specifications = []
                li_tags = specifications_list.find_all("li")
                for li in li_tags:
                    spec_text = li.get_text(strip=True)
                    specifications.append(spec_text)
                product_data["Specifications"] = specifications

        driver.get(product_url)
        if response.status_code != 200:
            logging.error(f"Failed to retrieve product page {product_url}. HTTP Status Code: {response.status_code}")
            return product_data
       
        
        # Locate all `li` elements
        li_elements = driver.find_elements(By.CSS_SELECTOR, 'li.flex.flex-column.items-start.justify-between.w-100')
        
        selectedCategories = []
        for li in li_elements:
            # Extract the h3 text
            h3_text = li.find_element(By.CSS_SELECTOR, 'h3.ma0.tc1-title.w-90.w-auto-ns.mr2.f5-ns.f6').text

            
            try:
                # Try to find the button
                button = li.find_element(By.CSS_SELECTOR, 'button.pa0.b--solid.br2.ba.bg-transparent.pointer.b--theme-grey-darker.bw1.mb2.mr2.w-100.HzuYA')
                title = button.find_element(By.CSS_SELECTOR, 'div.tc2-title.tl.f6').text
                
            except Exception as e:
                # If button does not exist, look for the div
                div_element = li.find_element(By.CSS_SELECTOR, 'div.input.ph3.flex.justify-between.items-center')
                title = div_element.find_element(By.TAG_NAME, 'span').text

            selectedCategories.append(h3_text + ':')
            selectedCategories.append(title)

        product_data["Categories"] = selectedCategories
        # product_data["Categories"] = selectedCategories
        # print (f'product_data["Prices"]-{product_data["Prices"]}')

        # Find the target div by its class
        # Wait for the clickable image to be present and click it
        image = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, IMAGE_SELECTOR))
        )
        image.click()
        
        
        # Wait for the modal to appear
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, MODAL_SELECTOR))
        )
        
        # Get the modal content
        modal = driver.find_element(By.CSS_SELECTOR, MODAL_SELECTOR)
        images_element = modal.find_element(By.CSS_SELECTOR, "div.w-100.w-60-ns")
        modal_html = images_element.get_attribute("outerHTML")
        # Parse modal content with BeautifulSoup
        soup = BeautifulSoup(modal_html, "html.parser")
        # print (soup)
        if soup:
            # Extract all <img> and <video> elements
            images = soup.find_all("img")
            videos = soup.find_all("video")

            # Extract URLs
            image_urls = [img["src"] for img in images if img.get("src") and ".jpg" in img["src"]]
            print(f'imgages-{image_urls}')
            # video_urls = []
            # for video in videos:
            #     # Check if <video> has a direct src or <source> tags
            #     if video.get('src'):
            #         video_urls.append(video['src'])
            #     else:
            #         source_tags = video.find_all("source")
            #         for source in source_tags:
            #             if source.get('src'):
            #                 video_urls.append(source['src'])
            product_data["Image_URL"] = image_urls

    except Exception as e:
        logging.error(f"Error extracting product details from {product_url}: {e}")

    return product_data

def main():
    # Ensure required columns exist in the DataFrame
    required_columns = ['Status','Classification', 'Image_URL','Name', 'Finish','Categories', 'Manufacturer_Resources', 'Dimensions&Measurements', 
                        'Included_components', 'Characteristics&Features','Electrical&Operational_Information', 
                        'Warranty&Product_Information', 'Features', 'Specifications']
    
    try:
        df = pd.read_csv(INPUT_CSV)
        logging.info(f"Loaded input CSV: {INPUT_CSV}")
        
        for col in required_columns:
            if col not in df.columns:
                df[col] = ''  # Add missing columns with empty string as default value
    except Exception as e:
        logging.error(f"Failed to read input CSV: {e}")
        return

    driver = initialize_webdriver()  # Open the browser once

    # Iterate over each row in the DataFrame
    i = 0
    for index, row in df.iterrows():
        i = i + 1
        model = row.get('Model#')  # Adjust column name if different
        print(i)
        if pd.isna(model) or model == "":  # Skip rows with nan or empty model number
            logging.warning(f"No valid model found in row {index}. Skipping.")
            df.at[index, 'Status'] = 'Invalid model'  # Mark as invalid
            continue
        if i == 0:
            time.sleep(10)
        else:
            time.sleep(2)
        if i == 6:
            break


        logging.info(f"Processing model: {model}")

        # Search for the product and get the detailed page link

        product_url = search_product(model)
        if not product_url:
            logging.warning(f"Skipping model {model} due to search failure.")
            df.at[index, 'Status'] = 'Not found'  # Mark as not found
            continue

        df.at[index, 'Status'] = 'Found'  # Mark as found
        # Extract product details from the detailed page
        details = extract_product_details(driver, product_url)
        # Update DataFrame columns
        for key, value in details.items():
            # Convert list values to a string
            if isinstance(value, list) and key == "Classification":
                value = ">>>".join(value)
            if isinstance(value, list) and key != "Classification":
                value = "; ".join(value)
            df.at[index, key] = value

        # Respectful scraping delay
        time.sleep(2)

    # Save the updated DataFrame to the output CSV
    try:
        df.to_csv(OUTPUT_CSV, index=False)
        logging.info(f"Saved updated data to {OUTPUT_CSV}")
    except Exception as e:
        logging.error(f"Failed to save output CSV: {e}")

if __name__ == "__main__":
    main()
    
