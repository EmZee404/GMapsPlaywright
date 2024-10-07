from playwright.sync_api import sync_playwright  
from dataclasses import dataclass, asdict, field
import pandas as pd
import openpyxl
import os
import sys

@dataclass
class Business:
    """Holds business data"""
    name: str = None
    address: str = None
    website: str = None
    phone_number: str = None
    reviews_count: int = None
    reviews_average: float = None
    latitude: float = None
    longitude: float = None

@dataclass
class BusinessList:
    """Holds list of Business objects and saves to both Excel and CSV"""
    business_list: list[Business] = field(default_factory=list)
    save_at: str = 'output'

    def dataframe(self) -> pd.DataFrame:
        """Transforms business_list to a pandas DataFrame"""
        return pd.json_normalize(
            (asdict(business) for business in self.business_list), sep="_"
        )

    def save_to_excel(self, filename: str):
        """Saves pandas DataFrame to an Excel (xlsx) file"""
        if not os.path.exists(self.save_at):
            os.makedirs(self.save_at)
        self.dataframe().to_excel(os.path.join(self.save_at, f"{filename}.xlsx"), index=False)

    def save_to_csv(self, filename: str):
        """Saves pandas DataFrame to a CSV file"""
        if not os.path.exists(self.save_at):
            os.makedirs(self.save_at)
        self.dataframe().to_csv(os.path.join(self.save_at, f"{filename}.csv"), index=False)

def extract_coordinates_from_url(url: str) -> tuple[float, float]:
    """Helper function to extract coordinates from a URL"""
    try:
        coordinates = url.split('/@')[-1].split('/')[0]
        latitude, longitude = map(float, coordinates.split(',')[:2])
        return latitude, longitude
    except (IndexError, ValueError) as e:
        print(f"Error extracting coordinates from URL '{url}': {e}")
        return None, None

def main():
    ########
    # Input 
    ########
    
    # Manually define search terms and their corresponding totals
    search_list = [
        "Coffee Shops United States"
        # Add more search terms as needed 
        ]
    
    totals = [
        50    # Coffee Shops
        
        # Ensure this list matches the length of search_list
    ]
    
    # Optional: If you want to assign a default total to some search terms,
    # you can define them here or ensure 'totals' has values for all 'search_list' items.

    # Validate that both lists have the same length
    if len(search_list) != len(totals):
        print("Error: The number of search terms and totals do not match.")
        sys.exit(1)

    ###########
    # Scraping
    ###########
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)  # Set headless=True for production
        page = browser.new_page()

        page.goto("https://www.google.com/maps", timeout=60000)
        # Wait added for development; adjust as needed
        page.wait_for_timeout(5000)
        
        for search_for_index, (search_for, total) in enumerate(zip(search_list, totals)):
            print(f"-----\n{search_for_index + 1} - {search_for}".strip())

            # Perform search
            search_box = page.locator('//input[@id="searchboxinput"]')
            search_box.fill(search_for)
            page.wait_for_timeout(3000)

            page.keyboard.press("Enter")
            page.wait_for_timeout(5000)

            # Hover to initiate listings load
            page.hover('//a[contains(@href, "https://www.google.com/maps/place")]')

            previously_counted = 0
            while True:
                # Scroll to load more listings
                page.mouse.wheel(0, 10000)
                page.wait_for_timeout(3000)

                listings_locator = page.locator('//a[contains(@href, "https://www.google.com/maps/place")]')
                current_count = listings_locator.count()

                if current_count >= total:
                    listings = listings_locator.all()[:total]
                    listings = [listing.locator("xpath=..") for listing in listings]
                    print(f"Total Scraped: {len(listings)}")
                    break
                else:
                    if current_count == previously_counted:
                        listings = listings_locator.all()
                        print(f"Arrived at all available listings.\nTotal Scraped: {len(listings)}")
                        break
                    else:
                        previously_counted = current_count
                        print(f"Currently Scraped: {current_count}")

            business_list = BusinessList()

            # Scraping individual listings
            for listing in listings:
                try:
                    listing.click()
                    page.wait_for_timeout(5000)

                    name_attribute = 'aria-label'
                    address_xpath = '//button[@data-item-id="address"]//div[contains(@class, "fontBodyMedium")]'
                    website_xpath = '//a[@data-item-id="authority"]//div[contains(@class, "fontBodyMedium")]'
                    phone_number_xpath = '//button[contains(@data-item-id, "phone:tel:")]//div[contains(@class, "fontBodyMedium")]'
                    review_count_xpath = '//button[@jsaction="pane.reviewChart.moreReviews"]//span'
                    reviews_average_xpath = '//div[@jsaction="pane.reviewChart.moreReviews"]//div[@role="img"]'
                    
                    business = Business()
                   
                    # Extract name
                    name = listing.get_attribute(name_attribute)
                    business.name = name if name and len(name) >= 1 else ""
                    
                    # Extract address
                    address_elements = page.locator(address_xpath)
                    business.address = address_elements.first.inner_text() if address_elements.count() > 0 else ""
                    
                    # Extract website
                    website_elements = page.locator(website_xpath)
                    business.website = website_elements.first.inner_text() if website_elements.count() > 0 else ""
                    
                    # Extract phone number
                    phone_elements = page.locator(phone_number_xpath)
                    business.phone_number = phone_elements.first.inner_text() if phone_elements.count() > 0 else ""
                    
                    # Extract reviews count
                    review_count_elements = page.locator(review_count_xpath)
                    if review_count_elements.count() > 0:
                        review_count_text = review_count_elements.first.inner_text().split()[0].replace(',', '').strip()
                        business.reviews_count = int(review_count_text)
                    else:
                        business.reviews_count = None
                        
                    # Extract reviews average
                    reviews_average_elements = page.locator(reviews_average_xpath)
                    if reviews_average_elements.count() > 0:
                        reviews_average_attr = reviews_average_elements.first.get_attribute(name_attribute)
                        if reviews_average_attr:
                            reviews_average_text = reviews_average_attr.split()[0].replace(',', '.').strip()
                            business.reviews_average = float(reviews_average_text)
                        else:
                            business.reviews_average = None
                    else:
                        business.reviews_average = None
                    
                    # Extract coordinates
                    coordinates = extract_coordinates_from_url(page.url)
                    if coordinates:
                        business.latitude, business.longitude = coordinates

                    business_list.business_list.append(business)
                except Exception as e:
                    print(f'Error occurred while scraping listing: {e}')
            
            #########
            # Output
            #########
            # Sanitize filename by replacing spaces and slashes
            filename_safe_search = f"google_maps_data_{search_for}".replace(' ', '_').replace('/', '_')
            business_list.save_to_excel(filename_safe_search)
            business_list.save_to_csv(filename_safe_search)

        browser.close()

if __name__ == "__main__":
    main()
