#!/bin/bash

# App Store Screenshot Generation Script for Snow Tracker
# Generates screenshots for all required App Store device sizes
# Requires Xcode and iOS simulators to be installed

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IOS_DIR="$PROJECT_DIR/ios"
SCREENSHOTS_DIR="$PROJECT_DIR/app_store_assets/screenshots"

# Create screenshots directory
mkdir -p "$SCREENSHOTS_DIR"

echo "🏂 Starting App Store screenshot generation for Snow Tracker"
echo "📁 Project directory: $PROJECT_DIR"
echo "📱 iOS project directory: $IOS_DIR"
echo "📸 Screenshots will be saved to: $SCREENSHOTS_DIR"

# Device configurations for App Store screenshots
# Apple requires specific device sizes:
# iPhone: 6.7" (iPhone 15 Pro Max), 6.5" (iPhone 11 Pro Max), 5.5" (iPhone 8 Plus)
# iPad: 12.9" (iPad Pro 6th gen), 11" (iPad Pro 4th gen)

declare -a IPHONE_DEVICES=(
    "iPhone 17 Pro Max"      # 6.7" - Primary requirement
    "iPhone 15 Pro Max"      # 6.7" - Backup
    "iPhone 11 Pro Max"      # 6.5" - Required size
    "iPhone 8 Plus"          # 5.5" - Legacy requirement
)

declare -a IPAD_DEVICES=(
    "iPad Pro (12.9-inch) (6th generation)"    # 12.9" - Primary requirement
    "iPad Pro (11-inch) (4th generation)"      # 11" - Secondary requirement
)

# Test scheme and target
SCHEME="PowderChaser"
TEST_TARGET="PowderChaserUITests"

# Function to check if simulator exists
check_simulator() {
    local device_name="$1"
    if xcrun simctl list devices | grep -q "$device_name"; then
        return 0
    else
        return 1
    fi
}

# Function to boot simulator if needed
boot_simulator() {
    local device_name="$1"
    local device_id

    # Get device ID
    device_id=$(xcrun simctl list devices | grep "$device_name" | grep -v "unavailable" | head -1 | sed -n 's/.*(\([^)]*\)).*/\1/p')

    if [ -z "$device_id" ]; then
        echo "❌ Could not find device ID for: $device_name"
        return 1
    fi

    # Check if already booted
    if xcrun simctl list devices | grep "$device_id" | grep -q "Booted"; then
        echo "✅ $device_name already booted"
        return 0
    fi

    echo "🚀 Booting simulator: $device_name ($device_id)"
    xcrun simctl boot "$device_id"

    # Wait for simulator to boot
    echo "⏳ Waiting for simulator to boot..."
    sleep 10

    return 0
}

# Function to run screenshot tests for a device
run_screenshot_tests() {
    local device_name="$1"
    local device_type="$2"  # "iphone" or "ipad"
    local output_dir="$SCREENSHOTS_DIR/$device_type/$device_name"

    echo ""
    echo "📱 Generating screenshots for: $device_name"
    echo "📂 Output directory: $output_dir"

    # Create output directory
    mkdir -p "$output_dir"

    # Check if device exists
    if ! check_simulator "$device_name"; then
        echo "⚠️  Simulator not found: $device_name"
        echo "💡 Available simulators:"
        xcrun simctl list devices | grep -E "(iPhone|iPad)" | head -10
        return 1
    fi

    # Boot simulator
    if ! boot_simulator "$device_name"; then
        echo "❌ Failed to boot simulator: $device_name"
        return 1
    fi

    # Set derived data path to avoid conflicts
    local derived_data_path="/tmp/PowderChaser_Screenshots_$(date +%s)"

    # Run the UI tests with screenshot generation
    echo "🧪 Running screenshot tests..."

    cd "$IOS_DIR"

    # Clean build directory first
    xcodebuild clean \
        -project PowderChaser.xcodeproj \
        -scheme "$SCHEME" \
        -destination "platform=iOS Simulator,name=$device_name" \
        -derivedDataPath "$derived_data_path"

    # Build the app
    echo "🔨 Building app..."
    xcodebuild build-for-testing \
        -project PowderChaser.xcodeproj \
        -scheme "$SCHEME" \
        -destination "platform=iOS Simulator,name=$device_name" \
        -derivedDataPath "$derived_data_path"

    # Run screenshot tests
    echo "📸 Taking screenshots..."
    xcodebuild test-without-building \
        -project PowderChaser.xcodeproj \
        -scheme "$SCHEME" \
        -destination "platform=iOS Simulator,name=$device_name" \
        -testPlan "ScreenshotTestPlan" \
        -only-testing:"PowderChaserUITests/AppStoreScreenshotTests" \
        -derivedDataPath "$derived_data_path" \
        -resultBundlePath "$output_dir/TestResults.xcresult"

    # Extract screenshots from test results
    echo "📤 Extracting screenshots..."
    extract_screenshots "$output_dir/TestResults.xcresult" "$output_dir"

    # Clean up derived data
    rm -rf "$derived_data_path"

    echo "✅ Screenshots generated for $device_name"
    return 0
}

# Function to extract screenshots from xcresult bundle
extract_screenshots() {
    local xcresult_path="$1"
    local output_dir="$2"

    if [ ! -d "$xcresult_path" ]; then
        echo "⚠️  Test results not found: $xcresult_path"
        return 1
    fi

    # Use xcparse or manual extraction to get screenshots
    # For now, we'll use xcrun to get attachments

    # Find screenshot attachments
    xcrun xcresulttool get --path "$xcresult_path" --format json > "$output_dir/results.json"

    # Extract attachment IDs and copy screenshot files
    # This is a simplified version - in practice you'd want to parse the JSON
    # and extract screenshots by test name for better organization

    local attachments_dir="$output_dir/attachments"
    mkdir -p "$attachments_dir"

    # Get list of attachments
    xcrun xcresulttool get --path "$xcresult_path" --list > "$output_dir/attachments_list.txt"

    # Copy screenshot files (this is a basic implementation)
    # In practice, you'd want to parse the results JSON to get specific screenshots
    find "$xcresult_path" -name "*.png" -exec cp {} "$attachments_dir/" \;
    find "$xcresult_path" -name "*.jpg" -exec cp {} "$attachments_dir/" \;

    echo "📁 Screenshots extracted to: $attachments_dir"
}

# Function to organize and rename screenshots
organize_screenshots() {
    echo ""
    echo "🗂️  Organizing screenshots..."

    # This function would:
    # 1. Rename screenshots based on test names
    # 2. Organize by device type and size
    # 3. Create App Store ready file names
    # 4. Generate metadata files

    # TODO: Implement screenshot organization logic
    echo "📝 TODO: Implement screenshot organization"
}

# Main execution
main() {
    echo "🔍 Checking Xcode installation..."
    if ! command -v xcodebuild &> /dev/null; then
        echo "❌ Xcode command line tools not found"
        echo "💡 Install with: xcode-select --install"
        exit 1
    fi

    echo "✅ Xcode found: $(xcodebuild -version | head -1)"

    # Change to iOS directory
    cd "$IOS_DIR"

    # Verify project exists
    if [ ! -f "PowderChaser.xcodeproj/project.pbxproj" ]; then
        echo "❌ PowderChaser.xcodeproj not found in $IOS_DIR"
        exit 1
    fi

    echo "✅ Project found"

    # Kill any existing simulators to start fresh
    echo "🧹 Cleaning up existing simulators..."
    xcrun simctl shutdown all
    sleep 2

    # Generate iPhone screenshots
    echo ""
    echo "📱 === GENERATING IPHONE SCREENSHOTS ==="
    for device in "${IPHONE_DEVICES[@]}"; do
        if run_screenshot_tests "$device" "iphone"; then
            echo "✅ iPhone screenshots completed: $device"
        else
            echo "⚠️  iPhone screenshots failed: $device"
        fi

        # Shutdown simulator between runs
        xcrun simctl shutdown all
        sleep 2
    done

    # Generate iPad screenshots
    echo ""
    echo "📱 === GENERATING IPAD SCREENSHOTS ==="
    for device in "${IPAD_DEVICES[@]}"; do
        if run_screenshot_tests "$device" "ipad"; then
            echo "✅ iPad screenshots completed: $device"
        else
            echo "⚠️  iPad screenshots failed: $device"
        fi

        # Shutdown simulator between runs
        xcrun simctl shutdown all
        sleep 2
    done

    # Organize final screenshots
    organize_screenshots

    echo ""
    echo "🎉 Screenshot generation complete!"
    echo "📁 Check results in: $SCREENSHOTS_DIR"
    echo ""
    echo "📋 Next steps:"
    echo "1. Review screenshots for quality"
    echo "2. Select best screenshots for each device size"
    echo "3. Upload to App Store Connect"
    echo "4. Test on actual devices if needed"
}

# Help function
show_help() {
    echo "Snow Tracker Screenshot Generator"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -h, --help     Show this help message"
    echo "  --iphone-only  Generate iPhone screenshots only"
    echo "  --ipad-only    Generate iPad screenshots only"
    echo "  --device NAME  Generate screenshots for specific device only"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Generate all screenshots"
    echo "  $0 --iphone-only                     # iPhone screenshots only"
    echo "  $0 --device \"iPhone 17 Pro Max\"      # Specific device only"
}

# Parse command line arguments
case "${1:-}" in
    -h|--help)
        show_help
        exit 0
        ;;
    --iphone-only)
        # Modify device arrays to only include iPhones
        IPAD_DEVICES=()
        main
        ;;
    --ipad-only)
        # Modify device arrays to only include iPads
        IPHONE_DEVICES=()
        main
        ;;
    --device)
        if [ -z "${2:-}" ]; then
            echo "❌ Device name required"
            show_help
            exit 1
        fi
        # Run for specific device only
        if run_screenshot_tests "$2" "custom"; then
            echo "✅ Screenshots completed for: $2"
        else
            echo "❌ Screenshots failed for: $2"
            exit 1
        fi
        ;;
    "")
        main
        ;;
    *)
        echo "❌ Unknown option: $1"
        show_help
        exit 1
        ;;
esac
