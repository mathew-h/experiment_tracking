# Power BI Dashboard Layout for Elemental Analysis Data

## Data Model Overview

### Required Tables & Relationships
```
ElementalAnalysis (Fact Table)
├── sample_id → SampleInfo.sample_id
├── analyte_id → Analyte.id
└── analyte_composition (measure)

SampleInfo (Dimension)
├── sample_id (PK)
├── rock_classification
├── state, country, locality
├── latitude, longitude
└── description

Analyte (Dimension)
├── id (PK)
├── analyte_symbol (e.g., FeO, SiO2, Al2O3)
└── unit (e.g., %, ppm)

ExternalAnalysis (Optional Dimension)
├── id (PK)
├── sample_id → SampleInfo.sample_id
├── analysis_date
├── laboratory
├── analyst
└── analysis_type
```

### Power BI Relationships
- **ElementalAnalysis** → **SampleInfo** (Many-to-One on `sample_id`)
- **ElementalAnalysis** → **Analyte** (Many-to-One on `analyte_id`)
- **ExternalAnalysis** → **SampleInfo** (Many-to-One on `sample_id`) - Optional for filtering

---

## Dashboard Layout Recommendations

### **Page 1: Elemental Composition Overview**

#### Top Section (Filters & KPIs)
- **Filter Panel (Left Sidebar)**
  - Slicer: `Sample ID` (multi-select)
  - Slicer: `Analyte Symbol` (multi-select)
  - Slicer: `Rock Classification`
  - Slicer: `Country/State`
  - Slicer: `Unit` (%, ppm, etc.)
  - Date Range: `Analysis Date` (from ExternalAnalysis if available)

- **KPI Cards (Top Row)**
  - Total Samples Analyzed
  - Total Analytes Measured
  - Average Analytes per Sample
  - Samples with Complete Analysis

#### Main Visualizations (Grid Layout)

**Row 1:**
1. **Matrix/Table Visual** (Large, Left)
   - Rows: `Sample ID`
   - Columns: `Analyte Symbol with Unit` (e.g., "FeO (%)", "SiO2 (%)", "Au (ppm)")
   - Values: `Analyte Composition` (numeric, for calculations and formatting)
   - Format: Conditional formatting (color scale) for quick pattern recognition
   - Tooltip: Include sample metadata (location, rock type)
   - **Note:** Create calculated column `Analyte[Analyte with Unit]` to show units in headers (see Method 1 below)

2. **Bar Chart - Top Analytes by Frequency** (Right)
   - X-axis: `Analyte Symbol`
   - Y-axis: Count of samples with that analyte
   - Sort: Descending
   - Purpose: Identify most commonly measured analytes

**Row 2:**
3. **Clustered Column Chart - Composition by Rock Type** (Left)
   - X-axis: `Rock Classification`
   - Y-axis: `Analyte Composition` (Average)
   - Legend: `Analyte Symbol`
   - Purpose: Compare elemental profiles across rock types

4. **Scatter Plot - Correlation Analysis** (Right)
   - X-axis: One analyte (e.g., FeO)
   - Y-axis: Another analyte (e.g., Al2O3)
   - Color: `Rock Classification`
   - Size: `Analyte Composition` (if using different samples)
   - Purpose: Identify elemental correlations

**Row 3:**
5. **Heatmap - Sample vs Analyte Matrix** (Full Width)
   - Rows: `Sample ID`
   - Columns: `Analyte Symbol`
   - Values: `Analyte Composition` (color intensity)
   - Conditional Formatting: Color scale (e.g., blue-white-red)
   - Purpose: Visual pattern recognition across all samples

---

### **Page 2: Sample Comparison & Analysis**

#### Top Section
- **Filter Panel**: Same as Page 1
- **Comparison Mode Toggle**: Compare 2-5 selected samples side-by-side

#### Main Visualizations

**Row 1:**
1. **Multi-Row Card** (Left, Narrow)
   - Display selected sample metadata:
     - Sample ID
     - Rock Classification
     - Location (State, Country)
     - Number of Analytes Measured

2. **Stacked Bar Chart - Composition Profile** (Right, Wide)
   - X-axis: `Sample ID` (selected samples)
   - Y-axis: `Analyte Composition` (stacked)
   - Legend: `Analyte Symbol`
   - Purpose: Compare total composition across samples

**Row 2:**
3. **Waterfall Chart - Elemental Breakdown** (Full Width)
   - Category: `Analyte Symbol`
   - Y-axis: `Analyte Composition` (Sum)
   - Filter: Single sample selected
   - Purpose: Visualize major vs minor elements

4. **Line Chart - Composition Trends** (If time data available)
   - X-axis: `Analysis Date` (from ExternalAnalysis)
   - Y-axis: `Analyte Composition`
   - Series: `Analyte Symbol`
   - Purpose: Track changes over time (if same sample analyzed multiple times)

**Row 3:**
5. **Table Visual - Detailed Data** (Full Width)
   - Columns:
     - Sample ID
     - Analyte Symbol
     - Analyte Composition
     - Unit
     - Rock Classification
     - Location
     - Analysis Date (if available)
   - Sortable and filterable
   - Export capability

---

### **Page 3: Geographic & Statistical Analysis**

#### Top Section
- **Filter Panel**: Same as Page 1
- **Statistical Measures Toggle**: Mean, Median, Std Dev, Min, Max

#### Main Visualizations

**Row 1:**
1. **Map Visual** (Left, Wide)
   - Location: `Latitude`, `Longitude` from SampleInfo
   - Size: Number of analytes measured
   - Color: Average composition of selected analyte (via filter)
   - Tooltip: Sample ID, location, key analytes
   - Purpose: Geographic distribution of samples

2. **Box Plot - Distribution by Analyte** (Right, Narrow)
   - Category: `Analyte Symbol`
   - Values: `Analyte Composition`
   - Purpose: Show distribution, outliers, quartiles

**Row 2:**
3. **Histogram - Composition Distribution** (Left)
   - X-axis: `Analyte Composition` (bins)
   - Y-axis: Count of samples
   - Filter: Single analyte selected
   - Purpose: Understand distribution patterns

4. **Treemap - Composition by Category** (Right)
   - Category: `Rock Classification` → `Analyte Symbol`
   - Values: `Analyte Composition` (Sum)
   - Purpose: Hierarchical view of composition

**Row 3:**
5. **Statistical Summary Table** (Full Width)
   - Rows: `Analyte Symbol`
   - Columns: Count, Mean, Median, Std Dev, Min, Max, 25th Percentile, 75th Percentile
   - Purpose: Comprehensive statistical overview

---

### **Page 4: Drill-Down & Detail Analysis**

#### Top Section
- **Drill-Through Filters**: Sample ID, Analyte Symbol
- **Detail Level Toggle**: Sample → Analyte → Composition

#### Main Visualizations

**Row 1:**
1. **Card Visuals** (4-6 cards in a row)
   - Selected Sample ID
   - Selected Analyte Symbol
   - Composition Value
   - Unit
   - Rock Classification
   - Location

2. **Donut/Pie Chart - Composition Proportions** (Right)
   - Category: `Analyte Symbol`
   - Values: `Analyte Composition` (Sum)
   - Filter: Single sample
   - Purpose: Relative proportions of elements

**Row 2:**
3. **Ribbon Chart - Composition Ranking** (Full Width)
   - Y-axis: `Sample ID`
   - X-axis: `Analyte Composition`
   - Legend: `Analyte Symbol`
   - Purpose: Rank samples by composition

4. **Funnel Chart - Sample Coverage** (Right, Narrow)
   - Stages: Total Samples → Samples with Analysis → Samples with Selected Analyte
   - Purpose: Data completeness visualization

**Row 3:**
5. **Drill-Through Table** (Full Width)
   - All related data for selected sample/analyte
   - Include related ExternalAnalysis metadata (laboratory, analyst, date)
   - Include sample photos link (if available)

---

## Visual Type Recommendations by Use Case

### **For Pattern Recognition:**
- **Heatmap/Matrix**: Best for identifying patterns across samples and analytes
- **Treemap**: Hierarchical composition breakdown
- **Scatter Plot Matrix**: Multi-analyte correlations

### **For Comparison:**
- **Clustered Column Chart**: Compare multiple analytes across samples
- **Stacked Bar Chart**: Total composition comparison
- **Waterfall Chart**: Sequential composition breakdown

### **For Distribution Analysis:**
- **Box Plot**: Distribution and outliers
- **Histogram**: Frequency distribution
- **Violin Plot** (if available): Distribution shape

### **For Geographic Analysis:**
- **Map Visual**: Spatial distribution
- **Filled Map**: Regional patterns (if state/country data available)

### **For Time Series:**
- **Line Chart**: Trends over time
- **Area Chart**: Cumulative composition over time

---

## DAX Measures to Create

```dax
// Total Samples with Elemental Analysis
Total Samples Analyzed = DISTINCTCOUNT(ElementalAnalysis[sample_id])

// Average Analytes per Sample
Avg Analytes per Sample = 
    DIVIDE(
        COUNTROWS(ElementalAnalysis),
        DISTINCTCOUNT(ElementalAnalysis[sample_id])
    )

// Composition Percentage (if needed for normalization)
Composition % = 
    DIVIDE(
        SUM(ElementalAnalysis[analyte_composition]),
        CALCULATE(
            SUM(ElementalAnalysis[analyte_composition]),
            ALLSELECTED(ElementalAnalysis[analyte_id])
        )
    )

// Samples with Complete Analysis (all analytes)
Complete Analysis Samples = 
    VAR TotalAnalytes = DISTINCTCOUNT(Analyte[id])
    VAR SampleAnalytes = 
        CALCULATE(
            DISTINCTCOUNT(ElementalAnalysis[analyte_id]),
            ALLSELECTED()
        )
    RETURN
        IF(SampleAnalytes = TotalAnalytes, 1, 0)
```

---

## Displaying Units with Analyte Composition

Since units are stored in the `Analyte` table and related to `ElementalAnalysis` via `analyte_id`, you have several options to display units alongside composition values:

### **Method 1: Units in Column Headers (Recommended for Matrix/Table) ⭐**

**This is the simplest and cleanest approach!** Create a calculated column in the `Analyte` table that combines the symbol with the unit:

```dax
Analyte with Unit = Analyte[analyte_symbol] & " (" & Analyte[unit] & ")"
```

**Usage in Matrix/Table Visual:**
- Rows: `SampleInfo[sample_id]`
- Columns: `Analyte[Analyte with Unit]` (instead of `Analyte[analyte_symbol]`)
- Values: `ElementalAnalysis[analyte_composition]` (numeric, for calculations and formatting)

**Result:**
- Column headers display as: "FeO (%)", "SiO2 (%)", "Au (ppm)", etc.
- Values remain numeric for proper sorting, filtering, and conditional formatting
- No need for separate columns - clean and efficient!

**Advantages:**
- ✅ Single column per analyte (not two)
- ✅ Values remain numeric (can be used in calculations)
- ✅ Units clearly visible in headers
- ✅ Works perfectly with conditional formatting
- ✅ Maintains all numeric capabilities (sorting, filtering, aggregations)

### **Method 2: Calculated Column in ElementalAnalysis (Alternative)**

Create a calculated column in the `ElementalAnalysis` table that combines value and unit:

```dax
Composition with Unit = 
    VAR CompValue = ElementalAnalysis[analyte_composition]
    VAR UnitValue = RELATED(Analyte[unit])
    RETURN
        IF(
            ISBLANK(CompValue),
            BLANK(),
            FORMAT(CompValue, "0.00") & " " & UnitValue
        )
```

**Usage:**
- Use this column in **Table** and **Matrix** visuals instead of `analyte_composition`
- Displays as: "45.23 %" or "1234.56 ppm"
- Maintains numeric sorting capability if you keep the original column

### **Method 2: DAX Measure with Dynamic Unit Formatting**

Create a measure that formats the value with its unit:

```dax
Composition Formatted = 
    VAR CompValue = SUM(ElementalAnalysis[analyte_composition])
    VAR CurrentAnalyte = SELECTEDVALUE(ElementalAnalysis[analyte_id])
    VAR UnitValue = 
        IF(
            NOT ISBLANK(CurrentAnalyte),
            CALCULATE(
                SELECTEDVALUE(Analyte[unit]),
                FILTER(
                    Analyte,
                    Analyte[id] = CurrentAnalyte
                )
            ),
            BLANK()
        )
    RETURN
        IF(
            ISBLANK(CompValue) || ISBLANK(UnitValue),
            BLANK(),
            FORMAT(CompValue, "0.00") & " " & UnitValue
        )
```

**Usage:**
- Best for **Card** visuals showing single values
- Works when a single analyte is selected/filtered
- Returns text, so cannot be used for calculations

### **Method 3: Separate Unit Column in Visuals (Not Recommended)**

**Note:** This method creates two columns per analyte, which is unnecessary. Use Method 1 instead for a cleaner display.

If you still need separate columns for some reason:
- Values: `analyte_composition` (formatted as number)
- Add `Analyte[unit]` as a separate column next to values
- Format: Right-align composition, left-align unit

### **Method 4: Custom Format String (Axis Labels)**

For chart axes, use custom format strings in the visual formatting pane:

1. Select the visual (e.g., Column Chart)
2. Go to **Format** → **Y-axis** (or X-axis)
3. Under **Title**, add unit in the title: "Composition (%)" or "Composition (ppm)"
4. Or create a dynamic title measure:

```dax
Axis Title with Unit = 
    VAR SelectedUnit = SELECTEDVALUE(Analyte[unit])
    RETURN
        IF(
            ISBLANK(SelectedUnit),
            "Composition",
            "Composition (" & SelectedUnit & ")"
        )
```

**Note:** This works best when filtering to a single analyte type, as different analytes may have different units.

### **Method 5: Tooltip Enhancement**

Add unit information to tooltips for better context:

1. Create a tooltip measure:

```dax
Tooltip Composition = 
    VAR CompValue = SUM(ElementalAnalysis[analyte_composition])
    VAR AnalyteName = SELECTEDVALUE(Analyte[analyte_symbol])
    VAR UnitValue = SELECTEDVALUE(Analyte[unit])
    RETURN
        AnalyteName & ": " & 
        FORMAT(CompValue, "0.00") & " " & UnitValue
```

2. Add this measure to the **Tooltip** field in your visual
3. Enable **Tooltip** in visual formatting options

### **Method 6: Conditional Formatting with Unit Context**

For matrix visuals with mixed units, you can combine Method 1 (units in headers) with conditional formatting:

1. Use Method 1 to show units in column headers: `Analyte[Analyte with Unit]`

2. Create a measure for conditional formatting based on unit type:

```dax
Unit for Formatting = SELECTEDVALUE(Analyte[unit])
```

3. In the Matrix visual:
   - Columns: `Analyte[Analyte with Unit]` (shows units in headers)
   - Values: `analyte_composition` (numeric)
   - Conditional Formatting → Background color
   - Optionally use `Unit for Formatting` to apply different color scales for different unit types (%, ppm, etc.)

### **Recommended Approach by Visual Type**

| Visual Type | Recommended Method | Notes |
|------------|-------------------|-------|
| **Matrix** | **Method 1** (Units in Headers) ⭐ | **Best approach** - units in column headers, values remain numeric |
| **Table** | **Method 1** (Units in Headers) ⭐ | Same as Matrix - clean single-column display |
| **Card** | Method 2 (DAX Measure) | Single value display with unit in text |
| **Bar/Column Chart** | Method 4 (Axis Title) | Unit in axis label, filter by analyte |
| **Scatter Plot** | Method 4 (Axis Title) | Different units on X/Y axes |
| **Tooltip** | Method 5 (Tooltip Measure) | Contextual unit information |

### **Handling Mixed Units in Same Visual**

When displaying multiple analytes with different units (%, ppm, etc.):

1. **Option A: Group by Unit**
   - Add `Analyte[unit]` as a legend or category
   - Create separate visuals for each unit type
   - Use slicers to filter by unit

2. **Option B: Normalize Values**
   - Use the normalization approach from Data Preparation Tips
   - Convert all to a common unit (e.g., %)
   - Display normalized values with common unit label

3. **Option C: Multi-Column Display**
   - Show original value and normalized value side-by-side
   - Label columns clearly: "Composition (Original Unit)" and "Composition (Normalized %)"

### **Example: Complete Matrix Setup with Units (Recommended Method)**

1. **Create Calculated Column in Analyte Table:**
```dax
Analyte with Unit = Analyte[analyte_symbol] & " (" & Analyte[unit] & ")"
```

2. **In Matrix Visual:**
   - Rows: `SampleInfo[sample_id]`
   - Columns: `Analyte[Analyte with Unit]` ← Use the new calculated column here
   - Values: `ElementalAnalysis[analyte_composition]` ← Keep numeric for calculations
   - Format → Values: 
     - Number format: 2 decimal places
     - Increase font size, right-align numbers

3. **Add Conditional Formatting:**
   - Use `analyte_composition` (numeric) for background color scale
   - Values display as numbers, units are in column headers
   - Result: Clean matrix with "FeO (%)", "SiO2 (%)", etc. as column headers

**Why This Works Better:**
- Column headers show: "FeO (%)", "SiO2 (%)", "Au (ppm)"
- Cell values remain numeric: 45.23, 67.89, 1234.56
- No need for two columns per analyte
- All numeric operations (sorting, filtering, conditional formatting) work perfectly

---

## Data Preparation Tips

1. **Pivot Preparation**: Consider creating a pre-pivoted view in Power Query if you need wide format (samples as rows, analytes as columns)

2. **Unit Normalization**: Create calculated columns to normalize units if mixing % and ppm:
   ```dax
   Normalized Composition = 
       IF(
           Analyte[unit] = "ppm",
           ElementalAnalysis[analyte_composition] / 10000,
           ElementalAnalysis[analyte_composition]
       )
   ```

3. **Missing Data Handling**: Use conditional formatting or visual settings to clearly indicate missing/null values

4. **Hierarchical Drill-Down**: Create hierarchies:
   - Country → State → Locality → Sample ID
   - Rock Classification → Sample ID → Analyte

5. **Tooltip Enhancement**: Add rich tooltips with:
   - Sample description
   - Analysis metadata (laboratory, analyst, date)
   - Related experiment count
   - Geographic coordinates

---

## Recommended Color Schemes

- **Composition Values**: Blue-White-Red diverging (centered at zero or mean)
- **Rock Types**: Qualitative palette (distinct colors)
- **Analytes**: Categorical palette (10-15 distinct colors)
- **Geographic**: Sequential (light to dark) for concentration values

---

## Performance Optimization

1. **Aggregation**: Pre-aggregate at sample-analyte level if dealing with large datasets
2. **DirectQuery vs Import**: Use Import mode for better performance with calculated measures
3. **Incremental Refresh**: Set up incremental refresh if data grows over time
4. **Summarization**: Disable auto-summarization on high-cardinality columns (sample_id)

---

## Export & Sharing Features

- **Export to Excel**: Enable for detailed tables
- **Bookmarks**: Create bookmarks for common filter combinations
- **Drill-Through Pages**: Set up drill-through from overview to detail pages
- **URL Filters**: Enable for sharing specific views via URL parameters

