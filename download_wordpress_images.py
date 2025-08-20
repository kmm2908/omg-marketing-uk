#!/usr/bin/env python3
"""
WordPress Image Downloader for Hugo Migration
Downloads all images from a WordPress site and organizes them for Hugo.
"""

import requests
import os
import json
import re
from urllib.parse import urljoin, urlparse
from pathlib import Path
import time
from PIL import Image
import hashlib
from bs4 import BeautifulSoup

class WordPressImageDownloader:
    def __init__(self, wordpress_url, hugo_static_path):
        self.wordpress_url = wordpress_url.rstrip('/')
        self.hugo_static_path = Path(hugo_static_path)
        self.images_path = self.hugo_static_path / 'images'
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Create directories
        self.images_path.mkdir(parents=True, exist_ok=True)
        
        # Inventory tracking
        self.downloaded_images = {}
        self.failed_downloads = []
        self.url_mapping = {}
        
    def get_all_page_urls(self):
        """Get all page URLs from the WordPress site"""
        urls = set()
        
        try:
            # Try to get sitemap first
            sitemap_urls = [
                f"{self.wordpress_url}/sitemap.xml",
                f"{self.wordpress_url}/wp-sitemap.xml",
                f"{self.wordpress_url}/sitemap_index.xml"
            ]
            
            for sitemap_url in sitemap_urls:
                try:
                    response = self.session.get(sitemap_url, timeout=10)
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.content, 'xml')
                        for loc in soup.find_all('loc'):
                            urls.add(loc.text)
                        print(f"✓ Found {len(urls)} URLs from sitemap: {sitemap_url}")
                        break
                except:
                    continue
                    
        except Exception as e:
            print(f"Could not get sitemap: {e}")
        
        # Fallback: crawl main pages
        if not urls:
            main_pages = [
                self.wordpress_url,
                f"{self.wordpress_url}/about",
                f"{self.wordpress_url}/services", 
                f"{self.wordpress_url}/contact",
                f"{self.wordpress_url}/blog"
            ]
            urls.update(main_pages)
            
        return list(urls)
    
    def extract_images_from_page(self, page_url):
        """Extract all image URLs from a page"""
        images = set()
        
        try:
            print(f"Scanning page: {page_url}")
            response = self.session.get(page_url, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Find all img tags
                for img in soup.find_all('img'):
                    src = img.get('src')
                    if src:
                        full_url = urljoin(page_url, src)
                        images.add(full_url)
                    
                    # Also check data-src for lazy loading
                    data_src = img.get('data-src')
                    if data_src:
                        full_url = urljoin(page_url, data_src)
                        images.add(full_url)
                
                # Find CSS background images
                for element in soup.find_all(style=True):
                    style = element.get('style', '')
                    bg_images = re.findall(r'background-image:\s*url\(["\']?([^"\')]+)["\']?\)', style)
                    for bg_img in bg_images:
                        full_url = urljoin(page_url, bg_img)
                        images.add(full_url)
                        
        except Exception as e:
            print(f"Error scanning {page_url}: {e}")
            
        return images
    
    def get_wordpress_upload_images(self):
        """Try to get images from common WordPress upload directories"""
        images = set()
        upload_paths = [
            '/wp-content/uploads/',
            '/wp-includes/images/',
            '/wp-admin/images/'
        ]
        
        for upload_path in upload_paths:
            try:
                # Try to access directory listing (if enabled)
                dir_url = f"{self.wordpress_url}{upload_path}"
                response = self.session.get(dir_url, timeout=10)
                
                if response.status_code == 200 and 'Index of' in response.text:
                    soup = BeautifulSoup(response.content, 'html.parser')
                    for link in soup.find_all('a'):
                        href = link.get('href', '')
                        if any(href.lower().endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg']):
                            full_url = urljoin(dir_url, href)
                            images.add(full_url)
                            
            except Exception as e:
                print(f"Could not access {upload_path}: {e}")
                
        return images
    
    def download_image(self, image_url, optimize=True):
        """Download and optionally optimize a single image"""
        try:
            # Parse URL to get filename
            parsed_url = urlparse(image_url)
            original_filename = os.path.basename(parsed_url.path)
            
            if not original_filename:
                # Generate filename from URL hash
                url_hash = hashlib.md5(image_url.encode()).hexdigest()[:8]
                original_filename = f"image_{url_hash}.jpg"
            
            # Preserve WordPress folder structure
            wp_path = parsed_url.path
            if '/wp-content/uploads/' in wp_path:
                # Extract year/month structure
                path_parts = wp_path.split('/wp-content/uploads/')[1].split('/')
                if len(path_parts) > 1:
                    subdir = '/'.join(path_parts[:-1])
                    local_dir = self.images_path / subdir
                    local_dir.mkdir(parents=True, exist_ok=True)
                    local_path = local_dir / original_filename
                else:
                    local_path = self.images_path / original_filename
            else:
                local_path = self.images_path / original_filename
            
            # Skip if already downloaded
            if local_path.exists():
                print(f"✓ Already exists: {local_path.name}")
                self.url_mapping[image_url] = str(local_path.relative_to(self.hugo_static_path))
                return True
            
            # Download image
            print(f"Downloading: {image_url}")
            response = self.session.get(image_url, timeout=30)
            
            if response.status_code == 200:
                # Save original
                with open(local_path, 'wb') as f:
                    f.write(response.content)
                
                # Optimize if requested
                if optimize and local_path.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                    self.optimize_image(local_path)
                
                # Record mapping
                relative_path = str(local_path.relative_to(self.hugo_static_path))
                self.url_mapping[image_url] = relative_path
                self.downloaded_images[image_url] = {
                    'original_url': image_url,
                    'local_path': str(local_path),
                    'relative_path': relative_path,
                    'size': local_path.stat().st_size
                }
                
                print(f"✓ Downloaded: {local_path.name}")
                return True
            else:
                print(f"✗ Failed to download {image_url}: HTTP {response.status_code}")
                self.failed_downloads.append({'url': image_url, 'error': f'HTTP {response.status_code}'})
                
        except Exception as e:
            print(f"✗ Error downloading {image_url}: {e}")
            self.failed_downloads.append({'url': image_url, 'error': str(e)})
            
        return False
    
    def optimize_image(self, image_path):
        """Optimize image for web performance"""
        try:
            with Image.open(image_path) as img:
                # Convert RGBA to RGB for JPEG
                if image_path.suffix.lower() == '.jpg' and img.mode == 'RGBA':
                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                    rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = rgb_img
                
                # Resize if too large (max 1920px width)
                if img.width > 1920:
                    ratio = 1920 / img.width
                    new_height = int(img.height * ratio)
                    img = img.resize((1920, new_height), Image.Resampling.LANCZOS)
                
                # Save optimized
                save_kwargs = {'optimize': True}
                if image_path.suffix.lower() in ['.jpg', '.jpeg']:
                    save_kwargs['quality'] = 85
                elif image_path.suffix.lower() == '.png':
                    save_kwargs['optimize'] = True
                
                img.save(image_path, **save_kwargs)
                print(f"  ✓ Optimized: {image_path.name}")
                
        except Exception as e:
            print(f"  ⚠ Could not optimize {image_path.name}: {e}")
    
    def save_inventory(self):
        """Save download inventory and URL mappings"""
        # Save detailed inventory
        inventory_file = self.hugo_static_path / 'image_inventory.json'
        with open(inventory_file, 'w') as f:
            json.dump({
                'downloaded_images': self.downloaded_images,
                'failed_downloads': self.failed_downloads,
                'url_mapping': self.url_mapping,
                'stats': {
                    'total_downloaded': len(self.downloaded_images),
                    'total_failed': len(self.failed_downloads),
                    'total_size_bytes': sum(img['size'] for img in self.downloaded_images.values())
                }
            }, f, indent=2)
        
        # Save simple URL mapping for content migration
        mapping_file = self.hugo_static_path / 'url_mapping.json' 
        with open(mapping_file, 'w') as f:
            json.dump(self.url_mapping, f, indent=2)
        
        print(f"\n✓ Saved inventory to: {inventory_file}")
        print(f"✓ Saved URL mapping to: {mapping_file}")
    
    def run(self, optimize_images=True):
        """Main execution method"""
        print(f"🚀 Starting WordPress image download from: {self.wordpress_url}")
        print(f"📁 Saving to: {self.images_path}")
        
        # Step 1: Get all page URLs
        print("\n📄 Finding all pages...")
        page_urls = self.get_all_page_urls()
        print(f"Found {len(page_urls)} pages to scan")
        
        # Step 2: Extract images from all pages
        print("\n🖼  Extracting images from pages...")
        all_images = set()
        for page_url in page_urls:
            page_images = self.extract_images_from_page(page_url)
            all_images.update(page_images)
            time.sleep(0.5)  # Be respectful
        
        # Step 3: Try to get additional images from upload directories
        print("\n📁 Checking WordPress upload directories...")
        upload_images = self.get_wordpress_upload_images()
        all_images.update(upload_images)
        
        # Filter for actual image URLs
        image_extensions = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.ico')
        filtered_images = {img for img in all_images if any(img.lower().endswith(ext) for ext in image_extensions)}
        
        print(f"\n📊 Found {len(filtered_images)} images to download")
        
        # Step 4: Download all images
        print("\n⬇️  Downloading images...")
        success_count = 0
        for i, image_url in enumerate(filtered_images, 1):
            print(f"[{i}/{len(filtered_images)}] ", end="")
            if self.download_image(image_url, optimize=optimize_images):
                success_count += 1
            time.sleep(0.2)  # Be respectful
        
        # Step 5: Save inventory
        print(f"\n📋 Saving inventory...")
        self.save_inventory()
        
        # Final report
        print(f"\n🎉 Download Complete!")
        print(f"✅ Successfully downloaded: {success_count} images")
        print(f"❌ Failed downloads: {len(self.failed_downloads)}")
        print(f"📁 Images saved to: {self.images_path}")
        
        if self.failed_downloads:
            print("\n⚠️  Failed downloads:")
            for fail in self.failed_downloads[:10]:  # Show first 10
                print(f"  - {fail['url']}: {fail['error']}")

def main():
    # Configuration
    wordpress_url = "https://omgmarketinguk.com"
    hugo_static_path = "/Volumes/MediaSSD/projects/Web Design/omg-marketing-uk/static"
    
    # Run downloader
    downloader = WordPressImageDownloader(wordpress_url, hugo_static_path)
    downloader.run(optimize_images=True)

if __name__ == "__main__":
    main()