#!/bin/bash

# WordPress Image Downloader - Simple Version
# Downloads images from WordPress site using wget

WORDPRESS_URL="https://omgmarketinguk.com"
STATIC_DIR="/Volumes/MediaSSD/projects/Web Design/omg-marketing-uk/static"
IMAGES_DIR="$STATIC_DIR/images"

echo "🚀 Starting WordPress image download..."
echo "📁 WordPress URL: $WORDPRESS_URL"
echo "💾 Target directory: $IMAGES_DIR"

# Create images directory
mkdir -p "$IMAGES_DIR"
cd "$IMAGES_DIR"

echo ""
echo "⬇️  Downloading images..."

# Download from common WordPress paths
echo "📁 Downloading from /wp-content/uploads/..."
wget -r -np -nd -A "*.jpg,*.jpeg,*.png,*.gif,*.webp,*.svg" \
     --user-agent="Mozilla/5.0 (compatible; Hugo Migration Bot)" \
     --wait=0.5 \
     --limit-rate=200k \
     -e robots=off \
     "$WORDPRESS_URL/wp-content/uploads/" \
     2>/dev/null || echo "⚠️  Could not access wp-content/uploads"

echo "📁 Downloading from /wp-includes/images/..."
wget -r -np -nd -A "*.jpg,*.jpeg,*.png,*.gif,*.webp,*.svg" \
     --user-agent="Mozilla/5.0 (compatible; Hugo Migration Bot)" \
     --wait=0.5 \
     --limit-rate=200k \
     -e robots=off \
     "$WORDPRESS_URL/wp-includes/images/" \
     2>/dev/null || echo "⚠️  Could not access wp-includes/images"

# Try to download from main pages
echo "🔍 Scanning main pages for additional images..."
for page in "" "/about" "/services" "/contact" "/blog"; do
    echo "Scanning: $WORDPRESS_URL$page"
    
    # Get page content and extract image URLs
    curl -s -A "Mozilla/5.0 (compatible; Hugo Migration Bot)" "$WORDPRESS_URL$page" | \
    grep -Eio '<img[^>]+src[[:space:]]*=[[:space:]]*["\047]([^"\047>]+)["\047]' | \
    sed -E 's/.*src[[:space:]]*=[[:space:]]*["\047]([^"\047>]+)["\047].*/\1/' | \
    while read -r img_url; do
        # Convert relative URLs to absolute
        if [[ $img_url == /* ]]; then
            img_url="$WORDPRESS_URL$img_url"
        elif [[ $img_url != http* ]]; then
            img_url="$WORDPRESS_URL/$img_url"
        fi
        
        # Download image
        filename=$(basename "$img_url" | cut -d'?' -f1)
        if [[ -n "$filename" && "$filename" =~ \.(jpg|jpeg|png|gif|webp|svg)$ ]]; then
            echo "  Downloading: $filename"
            wget -q --user-agent="Mozilla/5.0 (compatible; Hugo Migration Bot)" \
                 --timeout=10 \
                 -O "$filename" \
                 "$img_url" || echo "    ❌ Failed to download $filename"
        fi
    done
    
    sleep 1  # Be respectful
done

# Count downloaded files
image_count=$(find "$IMAGES_DIR" -type f \( -name "*.jpg" -o -name "*.jpeg" -o -name "*.png" -o -name "*.gif" -o -name "*.webp" -o -name "*.svg" \) | wc -l)

echo ""
echo "✅ Download complete!"
echo "📊 Downloaded $image_count images to: $IMAGES_DIR"
echo ""
echo "📋 To see what was downloaded:"
echo "   ls -la '$IMAGES_DIR'"
echo ""
echo "🔄 Next steps:"
echo "   1. Review downloaded images"
echo "   2. Update Hugo content to reference /images/filename.ext"
echo "   3. Run 'hugo server' to test"