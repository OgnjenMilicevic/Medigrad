import pandas as pd
import numpy as np
from collections import Counter
import core

def describe_df(df, type_dict=None, pre_type_dict=None, norm_dict=None, len_ord=3):
    """
    Generates detailed descriptive statistics for different variable types in a DataFrame.
    """
    if type_dict is None:
        type_dict = core.characterize_columns(df, pre_type_dict)

    results = {}

    # Constants
    const_cols = [k for k, v in type_dict.items() if v=="constant"]
    if const_cols:
        df_const = df[const_cols]
        # The mode retyrns a dataframe with multiple rows (possibly multiple modes)
        out_const = pd.DataFrame({"count": df_const.count(), "value": df_const.mode().iloc[0,:]})
        out_const.index.name = "Variable"
        results["Constant"] = out_const

    # Binary categorical
    bin_cols = [k for k, v in type_dict.items() if v=="binary_categorical"]
    if bin_cols:
        bin_dict = {}
        for col in bin_cols:
            ser_bin = df[col]
            counts = ser_bin.value_counts()
            counts = counts.sort_index(kind="stable")
            counts = counts.sort_values(ascending=False, kind="stable")
            nonmissing = ser_bin.count()
            bin_dict[col] = {"count": nonmissing}
            if len(counts) > 0:
                bin_dict[col].update({
                    "Major value": counts.index[0], 
                    "Major value count": counts.iloc[0], 
                    "Major value frequency (%)": 100*counts.iloc[0]/nonmissing if nonmissing > 0 else 0
                })
            if len(counts) > 1:
                 bin_dict[col].update({
                    "Minor value": counts.index[1], 
                    "Minor value count": counts.iloc[1], 
                    "Minor value frequency (%)": 100*counts.iloc[1]/nonmissing if nonmissing > 0 else 0
                })
        out_bin = pd.DataFrame(bin_dict).T
        out_bin.index.name = "Variable"
        results["Binary Categorical"] = out_bin

    # Ordinal/Multinomial categorical
    multi_cols = [k for k, v in type_dict.items() if v in ("multinomial_categorical","ordinal","maybe_ordinal")]
    if multi_cols:
        multi_dict = {}
        for col in multi_cols:
            ser_multi = df[col]
            counts = ser_multi.value_counts()
            # value_counts() orders by frequency but breaks ties arbitrarily,
            # which makes equal-count levels swap order across platforms/runs.
            # Sort deterministically: descending count, then by the value.
            counts = counts.sort_index(kind="stable")                      # secondary key: value
            counts = counts.sort_values(ascending=False, kind="stable")    # primary key: count
            if len(counts) < 3:
                raise ValueError(f"Multinomial categorical or ordinal variable {col} has {len(counts)} levels: {counts.index}")
            nonmissing = ser_multi.count()
            multi_dict[col] = {"Count": nonmissing, "Levels": sum(pd.notna(counts.index))}
            for i in range(min(len_ord, len(counts))):
                multi_dict[col][f"Value {i+1}"] = counts.index[i]
                multi_dict[col][f"Value {i+1} count"] = counts.iloc[i]
                multi_dict[col][f"Value {i+1} frequency (%)"] = 100*counts.iloc[i]/nonmissing if nonmissing > 0 else 0
        out_multi = pd.DataFrame.from_dict(multi_dict, orient='index')
        out_multi.index.name = "Variable"
        results["Multicategorical or Ordinal"] = out_multi

    # Scale
    scale_cols = [k for k, v in type_dict.items() if v=="scale"]
    if scale_cols:
        if norm_dict is None:
            norm_dict = core.check_normality(df, type_dict)
        df_scale = df[scale_cols]
        out_scale = df_scale.describe().T
        out_scale["IQR"] = out_scale["75%"] - out_scale["25%"]

        # Coefficient of variation (%) = std / mean * 100. Undefined when the
        # mean is ~0, in which case we leave it blank rather than divide by zero.
        cv_vals = []
        for ind in out_scale.index:
            m = out_scale.loc[ind, "mean"]
            sdv = out_scale.loc[ind, "std"]
            if pd.notna(m) and abs(m) > 1e-12:
                cv_vals.append(abs(sdv / m) * 100.0)
            else:
                cv_vals.append(float("nan"))
        out_scale["CV (%)"] = cv_vals

        norm_df = pd.DataFrame({k:v for k,v in norm_dict.items() if k in scale_cols})
        if not norm_df.empty:
             out_scale = pd.concat([out_scale, norm_df.T], axis=1)

        if "Normality" in out_scale.columns:
            out_scale["Representation"] = ""
            for ind, row in out_scale.iterrows():
                if pd.notna(row["Normality"]) and row["Normality"] == "normal":
                    out_scale.loc[ind, "Representation"] = f"{row['mean']:.2f} ± {row['std']:.2f}"
                else:
                    out_scale.loc[ind, "Representation"] = f"{row['50%']:.2f} ({row['25%']:.2f} - {row['75%']:.2f})"
        out_scale.index.name = "Variable"
        results["Scale"] = out_scale

        # Explicit, standalone normality-test table so the tests are clearly
        # reported on their own rather than only as columns in the scale table.
        if norm_dict:
            norm_rows = {}
            for col in scale_cols:
                info = norm_dict.get(col)
                if not info:
                    continue
                norm_rows[col] = {
                    "Shapiro-Wilk p-value": info.get("Shapiro-Wilk Normality Test p-value"),
                    "Kolmogorov-Smirnov (KS) p-value": info.get("Kolmogorov-Smirnov (KS) Normality Test p-value"),
                    "Conclusion (α=0.05)": "Normal" if info.get("Normality") == "normal" else "Non-normal",
                }
            if norm_rows:
                out_norm = pd.DataFrame.from_dict(norm_rows, orient="index")
                out_norm.index.name = "Variable"
                results["Normality Tests"] = out_norm

    return results


def describe_by_groups(df, group_cols, do_full=True, len_ord=3):
    results_dict = {}
    for group_col in group_cols:
        grouped = df.groupby(group_col)
        for val, sub_df in grouped:
            result = describe_df(sub_df, len_ord=len_ord)
            group_name = f"{group_col}=={val} (n={sub_df.shape[0]})"
            for ktype, res_df in result.items():
                if res_df is None: continue
                res_df.insert(loc=0, column="Group", value=group_name)
                if ktype in results_dict:
                    results_dict[ktype].append(res_df)
                else:
                    results_dict[ktype] = [res_df]

    if do_full:
        result = describe_df(df, len_ord=len_ord)
        group_name = "Full dataset"
        for ktype, res_df in result.items():
            if res_df is None: continue
            res_df.insert(loc=0, column="Group", value=group_name)
            results_dict[ktype].append(res_df)

    for ktype, df_list in results_dict.items():
        try:
            results_dict[ktype] = pd.concat(df_list).reset_index().set_index(["Group", "Variable"])
        except ValueError:
            results_dict[ktype] = None

    return results_dict

def _detect_outliers_iqr(series, iqr_multiplier):
    """Detects outliers using the IQR method."""
    q1 = series.quantile(0.25)
    q3 = series.quantile(0.75)
    iqr = q3 - q1
    lower_bound = q1 - iqr_multiplier * iqr
    upper_bound = q3 + iqr_multiplier * iqr
    return series[(series < lower_bound) | (series > upper_bound)]

def _detect_outliers_std(series, multiplier):
    """Detects outliers using the standard deviation method."""
    mean = series.mean()
    std = series.std()
    lower_bound = mean - multiplier * std
    upper_bound = mean + multiplier * std
    return series[(series < lower_bound) | (series > upper_bound)]

def _detect_outliers(series, multiplier=3.0):
    """
    Detects outliers in a numerical series.
    Uses IQR method by default. If IQR is 0, switches to standard deviation method.

    Args:
        series (pd.Series): A pandas Series of numerical data.
        multiplier (float): The multiplier for the range. Defaults to 3.0.

    Returns:
        list: A list of integer indices corresponding to the outliers in the series.
    """
    numeric_series = pd.to_numeric(series, errors='coerce').dropna()
    
    if numeric_series.empty:
        return []

    q1 = numeric_series.quantile(0.25)
    q3 = numeric_series.quantile(0.75)
    iqr = q3 - q1
    
    if iqr > 0:
        outliers = _detect_outliers_iqr(numeric_series, multiplier)
    else: # If IQR is 0, use std deviation method
        outliers = _detect_outliers_std(numeric_series, multiplier)
        
    return [int(i) for i in outliers.index.tolist()]

def _find_constant_increment_patterns(series):
    """
    Finds sequences of at least 4 elements in a numerical series that 
    follow a constant increment.

    Args:
        series (pd.Series): A pandas Series of numerical data.

    Returns:
        list: A list of tuples, each containing the start index, end index, 
              and the constant increment of a detected pattern.
    """
    patterns = []
    numbers = pd.to_numeric(series, errors='coerce').dropna()
    
    if len(numbers) < 4:
        return patterns

    number_list = numbers.tolist()
    index_list = numbers.index.tolist()

    i = 0
    while i <= len(number_list) - 4:
        diff1 = number_list[i+1] - number_list[i]
        diff2 = number_list[i+2] - number_list[i+1]
        diff3 = number_list[i+3] - number_list[i+2]
        
        if diff1 == diff2 and diff2 == diff3 and diff1 != 0:
            increment = diff1
            start_index = index_list[i]
            
            j = i + 3
            while j < len(number_list) - 1 and (number_list[j+1] - number_list[j]) == increment:
                j += 1
            
            end_index = index_list[j]
            patterns.append((int(start_index), int(end_index), float(increment)))
            i = j + 1
        else:
            i += 1
            
    return patterns

def qc_numerical_dataframe(df, outlier_multiplier=3.0):
    """
    Performs numerical quality control on a DataFrame.

    Args:
        df (pd.DataFrame): The DataFrame to be analyzed.
        outlier_multiplier (float): The multiplier for outlier detection. Defaults to 3.0.

    Returns:
        dict: A JSON serializable dictionary containing the QC report.
    """
    report = {
        'outlier_summary': {
            'by_column': {},
            'rows_with_outlier_counts': []
        },
        'constant_increment_patterns': {}
    }
    
    numerical_cols = df.select_dtypes(include=np.number).columns.tolist()
    all_outlier_indices = []

    for col in numerical_cols:
        outlier_indices = _detect_outliers(df[col], multiplier=outlier_multiplier)
        if outlier_indices:
            report['outlier_summary']['by_column'][col] = {
                'count': len(outlier_indices),
                'indices': outlier_indices
            }
            all_outlier_indices.extend(outlier_indices)
        
        patterns = _find_constant_increment_patterns(df[col])
        if patterns:
            report['constant_increment_patterns'][col] = patterns

    if all_outlier_indices:
        row_outlier_counts = Counter(all_outlier_indices)
        # Find rows that have an outlying number of outliers
        if row_outlier_counts:
            counts_series = pd.Series(row_outlier_counts)
            outlier_rows_indices = _detect_outliers(counts_series, multiplier=outlier_multiplier)
            
            # Report the rows whose outlier count is itself an outlier
            outlier_row_summary = {
                int(idx): int(counts_series.loc[idx]) for idx in outlier_rows_indices
            }
            
            # Sort by count descending
            sorted_outlier_rows = sorted(outlier_row_summary.items(), key=lambda item: item[1], reverse=True)
            report['outlier_summary']['rows_with_outlier_counts'] = sorted_outlier_rows


    return report