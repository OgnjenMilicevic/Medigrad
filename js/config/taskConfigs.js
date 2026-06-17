function fieldVariable1() {
  return {
    label: 'Variable 1',
    id: 'variable_1',
    type: 'select_headers',
    required: true,
  };
}

function fieldVariable2() {
  return {
    label: 'Variable 2',
    id: 'variable_2',
    type: 'select_headers',
    required: true,
  };
}

function fieldPairId() {
  return {
    label: 'Pair / Subject ID Column',
    id: 'pair_id_col',
    type: 'select_headers',
    optional: true,
  };
}

function fieldAlternative() {
  return {
    label: 'Alternative Hypothesis',
    id: 'alternative',
    type: 'select',
    options: [
      { label: 'Two-sided', value: 'two-sided' },
      { label: 'Greater', value: 'greater' },
      { label: 'Less', value: 'less' },
    ],
    default: 'two-sided',
    optional: true,
  };
}

function fieldAlpha() {
  return {
    label: 'Alpha',
    id: 'alpha',
    type: 'number',
    default: 0.05,
    optional: true,
  };
}

function fieldEqualVar() {
  return {
    label: 'Assume Equal Variances',
    id: 'equal_var',
    type: 'select',
    options: [
      { label: 'Yes', value: 'true' },
      { label: 'No', value: 'false' },
    ],
    default: 'true',
    optional: true,
  };
}

function fieldCorrection() {
  return {
    label: 'Yates Correction',
    id: 'correction',
    type: 'select',
    options: [
      { label: 'Auto / Default', value: '' },
      { label: 'Yes', value: 'true' },
      { label: 'No', value: 'false' },
    ],
    default: '',
    optional: true,
  };
}

function fieldZeroMethod() {
  return {
    label: 'Zero Method',
    id: 'zero_method',
    type: 'select',
    options: [
      { label: 'Wilcox', value: 'wilcox' },
      { label: 'Pratt', value: 'pratt' },
      { label: 'Z-split', value: 'zsplit' },
    ],
    default: 'wilcox',
    optional: true,
  };
}

function basicTwoVariableLevel(name = 'Basic') {
  return {
    name,
    fields: [fieldVariable1(), fieldVariable2()],
  };
}

function basicPairedLevel(name = 'Basic') {
  return {
    name,
    fields: [fieldVariable1(), fieldVariable2(), fieldPairId()],
  };
}

function fieldOutcomeSingle() {
  return {
    label: 'Outcome Column',
    id: 'outcome_column',
    type: 'select_headers',
    required: true,
  };
}

function fieldPredictorsMulti() {
  return {
    label: 'Predictor Columns',
    id: 'predictor_columns',
    type: 'select_headers',
    multiple: true,
    required: true,
  };
}

function fieldExcludeList() {
  return {
    label: 'Exclude from Predictors',
    id: 'exclude_list',
    type: 'select_headers',
    multiple: true,
    optional: true,
  };
}

function fieldDesirableList() {
  return {
    label: 'Force-In / Desirable Predictors',
    id: 'desirable_list',
    type: 'select_headers',
    multiple: true,
    optional: true,
  };
}

function fieldInteractions() {
  return {
    label: 'Interaction Terms',
    id: 'interactions',
    type: 'interaction_builder',
    optional: true,
  };
}

function fieldEstimationMethodRegression() {
  return {
    label: 'Estimation Method',
    id: 'estimation_method',
    type: 'select',
    default: 'MLE',
    options: [
      { value: 'MLE', label: 'MLE' },
      { value: 'Firth', label: 'Firth Penalized' },
    ],
    optional: true,
  };
}

function fieldSelectionMethod() {
  return {
    label: 'Selection Method',
    id: 'selection_method',
    type: 'select',
    default: 'direct',
    options: [
      { value: 'direct', label: 'Direct / Use Selected Predictors' },
      { value: 'stepwise', label: 'Stepwise Selection' },
    ],
    optional: true,
  };
}

function fieldStepwiseCriterion() {
  return {
    label: 'Stepwise Selection Criterion',
    id: 'stepwise_criterion',
    type: 'select',
    default: 'pvalue',
    options: [
      { value: 'pvalue', label: 'P-Value (Wald)' },
      { value: 'aic', label: 'AIC' },
      { value: 'bic', label: 'BIC' },
    ],
    optional: true,
  };
}

function fieldAddConstant() {
  return {
    label: 'Add Intercept / Constant',
    id: 'add_constant',
    type: 'select',
    options: [
      { label: 'Yes', value: 'true' },
      { label: 'No', value: 'false' },
    ],
    default: 'true',
    optional: true,
  };
}

function fieldReml() {
  return {
    label: 'Use REML',
    id: 'reml',
    type: 'select',
    options: [
      { label: 'Yes', value: 'true' },
      { label: 'No', value: 'false' },
    ],
    default: 'true',
    optional: true,
  };
}

function fieldMaxMissingPct() {
  return {
    label: 'Max Missing Data (%)',
    id: 'max_missing_pct',
    type: 'number',
    default: 80,
    optional: true,
  };
}

function fieldMaxVariancePct() {
  return {
    label: 'Max Single Value (%)',
    id: 'max_variance_pct',
    type: 'number',
    default: 95,
    optional: true,
  };
}

function fieldMaxPredictivePct() {
  return {
    label: 'Max Predictive Accuracy (%)',
    id: 'max_predictive_pct',
    type: 'number',
    default: 99,
    optional: true,
  };
}

function fieldSurvivalTimeCol() {
  return {
    label: 'Survival Time Column',
    id: 'survival_time_col',
    type: 'select_headers',
    required: true,
  };
}

function fieldSurvivalStatusCol() {
  return {
    label: 'Status / Event Column (1=event, 0=censored)',
    id: 'survival_status_col',
    type: 'select_headers',
    required: true,
  };
}

function fieldValueColumnsMulti(label = 'Outcome Columns') {
  return {
    label,
    id: 'value_columns',
    type: 'select_headers',
    multiple: true,
    required: true,
  };
}

function fieldGroupColumn() {
  return {
    label: 'Group Column',
    id: 'group_column',
    type: 'select_headers',
    required: true,
  };
}

function basicRegressionLevel(name = 'Basic') {
  return {
    name,
    fields: [fieldOutcomeSingle(), fieldPredictorsMulti()],
  };
}

function basicCoxLevel(name = 'Basic') {
  return {
    name,
    fields: [fieldSurvivalTimeCol(), fieldSurvivalStatusCol(), fieldPredictorsMulti()],
  };
}

function regressionDesignLevel(name = 'Predictor Design') {
  return {
    name,
    fields: [fieldInteractions(), fieldExcludeList(), fieldDesirableList()],
  };
}

function regressionAlgorithmLevel(name = 'Algorithm') {
  return {
    name,
    fields: [fieldSelectionMethod(), fieldStepwiseCriterion()],
  };
}

function regressionQcLevel(name = 'Quality Thresholds') {
  return {
    name,
    fields: [fieldMaxMissingPct(), fieldMaxVariancePct(), fieldMaxPredictivePct()],
  };
}

export const taskConfigs = {
  describe: {
    title: 'Descriptive Statistics',
    endpoint: 'description/describe',
    fields: [
      {
        label: 'Group By Columns (optional)',
        id: 'group_columns',
        type: 'select_headers',
        multiple: true,
        optional: true,
      },
    ],
  },

  correlation: {
    title: 'Correlation Analysis',
    endpoint: 'analysis/correlation',
    levels: [
      {
        name: 'Settings',
        fields: [
          {
            label: 'Method',
            id: 'method',
            type: 'select',
            options: [
              { label: 'Pearson', value: 'pearson' },
              { label: 'Spearman', value: 'spearman' },
            ],
            default: 'pearson',
            required: true,
          },
          {
            label: 'Columns (leave empty for all numeric)',
            id: 'columns',
            type: 'select_headers',
            multiple: true,
            optional: true,
          },
        ],
      },
    ],
  },

  ttest_ind: {
    title: 'Independent t-test',
    endpoint: 'analysis/tests/ttest-ind',
    levels: [
      basicTwoVariableLevel(),
      {
        name: 'Advanced',
        fields: [
          fieldEqualVar(), fieldAlternative(), fieldAlpha(),
          {
            label: 'Include Assumption Diagnostics',
            id: 'diagnostics',
            type: 'checkbox',
            default: false,
            optional: true,
          },
        ],
      },
    ],
  },

  ttest_paired: {
    title: 'Paired t-test',
    endpoint: 'analysis/tests/ttest-paired',
    levels: [
      basicPairedLevel(),
      {
        name: 'Advanced',
        fields: [fieldAlternative(), fieldAlpha()],
      },
    ],
  },

  mannwhitney: {
    title: 'Mann-Whitney U Test',
    endpoint: 'analysis/tests/mannwhitney',
    levels: [
      basicTwoVariableLevel(),
      {
        name: 'Advanced',
        fields: [fieldAlternative(), fieldAlpha()],
      },
    ],
  },

  wilcoxon: {
    title: 'Wilcoxon Signed-Rank Test',
    endpoint: 'analysis/tests/wilcoxon',
    levels: [
      basicPairedLevel(),
      {
        name: 'Advanced',
        fields: [fieldAlternative(), fieldZeroMethod(), fieldAlpha()],
      },
    ],
  },

  anova: {
    title: 'One-way ANOVA',
    endpoint: 'analysis/tests/anova',
    levels: [
      {
        name: 'General Linear Models',
        fields: [
          fieldGroupColumn(),
          {
            label: 'Numeric Outcome Column',
            id: 'value_column',
            type: 'select_headers',
            required: true,
          },
        ],
      },
      {
        name: 'Post-Hoc',
        fields: [
          {
            label: 'Post-Hoc Test (Tukey HSD, auto-runs when p < 0.05 and 3+ groups)',
            id: 'posthoc_method',
            type: 'select',
            options: [
              { label: 'Tukey HSD', value: 'tukey' },
            ],
            default: 'tukey',
            optional: true,
          },
        ],
      },
    ],
  },

  kruskal: {
    title: 'Kruskal-Wallis Test',
    endpoint: 'analysis/tests/kruskal',
    fields: [
      {
        label: 'Group Column',
        id: 'group_column',
        type: 'select_headers',
        required: true,
      },
      {
        label: 'Value / Outcome Column',
        id: 'value_column',
        type: 'select_headers',
        required: true,
      },
    ],
  },

  chi_square: {
    title: 'Chi-square Test of Independence',
    endpoint: 'analysis/tests/chi-square',
    levels: [
      basicTwoVariableLevel(),
      {
        name: 'Advanced',
        fields: [fieldCorrection(), fieldAlpha()],
      },
    ],
  },

  fisher_exact: {
    title: 'Fisher Exact Test',
    endpoint: 'analysis/tests/fisher-exact',
    levels: [
      basicTwoVariableLevel(),
      {
        name: 'Advanced',
        fields: [fieldAlternative(), fieldAlpha()],
      },
    ],
  },

  mcnemar: {
    title: "McNemar's Test (paired categorical)",
    endpoint: 'analysis/tests/mcnemar',
    fields: [
      fieldVariable1(),
      fieldVariable2(),
      {
        label: 'Method',
        id: 'method',
        type: 'select',
        options: [
          { label: 'Exact (binomial) — best for small samples', value: 'exact' },
          { label: 'Chi-square (with continuity correction)', value: 'chi2' },
        ],
        default: 'exact',
        required: true,
      },
      {
        label: 'Continuity Correction (chi-square method only)',
        id: 'correction',
        type: 'select',
        options: [
          { label: 'Yes (recommended)', value: 'true' },
          { label: 'No', value: 'false' },
        ],
        default: 'true',
        optional: true,
        showIf: { field: 'method', value: 'chi2' },
      },
    ],
  },

  ttest_one_sample: {
    title: 'One-sample t-test',
    endpoint: 'analysis/tests/ttest-one-sample',
    fields: [
      {
        label: 'Variable',
        id: 'variable_1',
        type: 'select_headers',
        required: true,
      },
      {
        label: 'Hypothesized value (population mean)',
        id: 'popmean',
        type: 'number',
        default: 0,
        required: true,
      },
      fieldAlternative(),
    ],
  },

  sign_test: {
    title: 'One-sample Sign Test',
    endpoint: 'analysis/tests/sign-test',
    fields: [
      {
        label: 'Variable',
        id: 'variable_1',
        type: 'select_headers',
        required: true,
      },
      {
        label: 'Hypothesized median',
        id: 'median',
        type: 'number',
        default: 0,
        required: true,
      },
      fieldAlternative(),
    ],
  },

  diagnostic_test: {
    title: 'Diagnostic Test Evaluation',
    endpoint: 'analysis/tests/diagnostic-test',
    fields: [
      {
        label: 'Test result variable',
        id: 'test_variable',
        type: 'select_headers',
        required: true,
      },
      {
        label: 'Value that means a POSITIVE test',
        id: 'test_positive',
        type: 'select_column_values',
        depends_on: 'test_variable',
        required: true,
      },
      {
        label: 'Disease/condition variable (gold standard)',
        id: 'disease_variable',
        type: 'select_headers',
        required: true,
      },
      {
        label: 'Value that means DISEASE PRESENT',
        id: 'disease_positive',
        type: 'select_column_values',
        depends_on: 'disease_variable',
        required: true,
      },
      {
        label: 'Assumed prevalence for adjusted PPV/NPV (optional, e.g. 0.02)',
        id: 'prevalence',
        type: 'number',
        optional: true,
      },
    ],
  },

  linear_regression: {
    title: 'Simple Linear Regression',
    endpoint: 'analysis/tests/linear-regression',
    fields: [
      {
        label: 'Outcome variable (Y)',
        id: 'outcome_variable',
        type: 'select_headers',
        required: true,
      },
      {
        label: 'Predictor variable (X)',
        id: 'predictor_variable',
        type: 'select_headers',
        required: true,
      },
    ],
  },

  chi_square_gof: {
    title: 'Chi-square Goodness-of-Fit (1-way)',
    endpoint: 'analysis/tests/chi-square-gof',
    fields: [
      {
        label: 'Input mode',
        id: 'mode',
        type: 'select',
        options: [
          { label: 'Use a column (count its categories)', value: 'column' },
          { label: 'Enter observed frequencies manually', value: 'manual' },
        ],
        default: 'column',
        required: true,
      },
      {
        label: 'Categorical column',
        id: 'variable_1',
        type: 'select_headers',
        required: true,
        showIf: { field: 'mode', value: 'column' },
      },
      {
        label: 'Observed frequencies (comma-separated, in category order)',
        id: 'observed',
        type: 'text',
        placeholder: 'e.g. 30, 25, 20, 25',
        showIf: { field: 'mode', value: 'manual' },
      },
      {
        label: 'Category names (optional, comma-separated, same order)',
        id: 'category_labels',
        type: 'text',
        placeholder: 'e.g. Red, Green, Blue, Yellow',
        optional: true,
        showIf: { field: 'mode', value: 'manual' },
      },
      {
        label: 'Expected frequencies (counts OR ratios; leave blank for equal/uniform)',
        id: 'expected',
        type: 'text',
        placeholder: 'e.g. 25, 25, 25, 25  or  1, 1, 2',
        optional: true,
      },
    ],
  },
};
