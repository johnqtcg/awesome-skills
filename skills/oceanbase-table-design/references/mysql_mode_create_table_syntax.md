# CREATE TABLE Syntax rules (OceanBase v4.5.0, MySQL Mode)

> **Nature**: This file is a **faithful BNF mirror** of OceanBase V4.5.0's official CREATE TABLE documentation, with no subjective rewriting.
> The official BNF itself has gaps (missing LIST partition enumeration syntax, `AUTO_INCREMENT_MODE` not included, dangling productions present).
> **Read [`doc-gaps.md`](doc-gaps.md) before generating DDL — its corrections take priority over this mirror.**

```
CREATE [hint_options] TABLE [IF NOT EXISTS] table_name
      (table_definition_list) [table_option_list] [partition_option] [[MERGE_ENGINE = {delete_insert | partial_update}] table_column_group_option] [IGNORE | REPLACE] [AS] select;

CREATE TABLE [IF NOT EXISTS] table_name
      LIKE table_name;

table_definition_list:
    table_definition [, table_definition ...]

table_definition:
      column_definition_list
    | [CONSTRAINT [constraint_name]] PRIMARY KEY index_desc
    | [CONSTRAINT [constraint_name]] UNIQUE {INDEX | KEY}
            [index_name] index_desc
    | [CONSTRAINT [constraint_name]] FOREIGN KEY
            [index_name] index_desc
            REFERENCES reference_definition
            [match_action][opt_reference_option_list]
    | [FULLTEXT] {INDEX | KEY} [index_name] [index_type] (key_part,...) [WITH PARSER tokenizer_option] [PARSER_PROPERTIES[=](parser_properties_list)]
      [index_option_list] [index_column_group_option]
    | index_json_clause
    | [CONSTRAINT [constraint_name]] CHECK(expression) constranit_state

column_definition_list:
    column_definition [, column_definition ...]

column_definition:
     column_name data_type
         [DEFAULT const_value] [AUTO_INCREMENT]
         [NULL | NOT NULL] [[PRIMARY] KEY] [UNIQUE [KEY]] [COMMENT string_value] [SKIP_INDEX(skip_index_option_list)]
   | column_name data_type
         [GENERATED ALWAYS] AS (expr) [VIRTUAL | STORED]
         [opt_generated_column_attribute]

skip_index_option_list:
    skip_index_option [,skip_index_option ...]

skip_index_option:
    MIN_MAX
    | SUM

index_desc:
   (column_desc_list) [index_type] [index_option_list]

match_action:
   MATCH {SIMPLE | FULL | PARTIAL}

opt_reference_option_list:
   reference_option [,reference_option ...]

reference_option:
   ON {DELETE | UPDATE} {RESTRICT | CASCADE | SET NULL | NO ACTION | SET DEFAULT}

tokenizer_option:
    SPACE
    | NGRAM
    | BENG
    | IK
    | NGRAM2

parser_properties_list:
    parser_properties, [parser_properties]

parser_properties:
    min_token_size = int_value
    | max_token_size = int_value
    | ngram_token_size = int_value
    | ik_mode = 'char_value'
    | min_ngram_size = int_value
    | max_ngram_size = int_value

key_part:
    {index_col_name [(length)] | (expr)} [ASC | DESC]

index_type:
    USING BTREE

index_option_list:
    index_option [ index_option ...]

index_option:
      [GLOBAL | LOCAL]
    | block_size
    | compression
    | STORING(column_name_list)
    | COMMENT string_value
    | STORAGE_CACHE_POLICY(storage_cache_policy_option)

table_option_list:
    table_option [ table_option ...]

table_option:
      [DEFAULT] {CHARSET | CHARACTER SET} [=] charset_name
    | [DEFAULT] COLLATE [=] collation_name
    | table_tablegroup
    | block_size
    | lob_inrow_threshold [=] num
    | compression
    | AUTO_INCREMENT [=] INT_VALUE
    | COMMENT string_value
    | ROW_FORMAT [=] REDUNDANT|COMPACT|DYNAMIC|COMPRESSED|DEFAULT
    | PCTFREE [=] num
    | parallel_clause
    | DUPLICATE_SCOPE [=] 'none|cluster'
    | TABLE_MODE [=] 'table_mode_value'
    | auto_increment_cache_size [=] INT_VALUE
    | READ {ONLY | WRITE}
    | ORGANIZATION [=] {INDEX | HEAP}
    | enable_macro_block_bloom_filter [=] {True | False}
    | DYNAMIC_PARTITION_POLICY [=] (dynamic_partition_policy_list)
    | SEMISTRUCT_ENCODING_TYPE [=] 'encoding' # Deprecated since V4.4.1; use SEMISTRUCT_PROPERTIES instead.
    | MICRO_BLOCK_FORMAT_VERSION [=] {1|2}
    | STORAGE_CACHE_POLICY (storage_cache_policy_option)
    | CLUSTER BY (column_name_list)    
    | HMS_CATALOG_NAME [=] string_value
    | COLUMN_NAME_CASE_SENSITIVE [=] {True | False}


parallel_clause:
    {NOPARALLEL | PARALLEL integer}

table_mode_value:
    NORMAL
    | QUEUING
    | MODERATE
    | SUPER
    | EXTREME

dynamic_partition_policy_list:
    dynamic_partition_policy_option [, dynamic_partition_policy_option ...]

dynamic_partition_policy_option:
    ENABLE = {true | false}
    | TIME_UNIT = {'hour' | 'day' | 'week' | 'month' | 'year'}
    | PRECREATE_TIME = {'-1' | '0' | 'n {hour | day | week | month | year}'}
    | EXPIRE_TIME = {'-1' | '0' | 'n {hour | day | week | month | year}'}
    | TIME_ZONE = {'default' | 'time_zone'}
    | BIGINT_PRECISION = {'none' | 'us' | 'ms' | 's'}

partition_option:
      PARTITION BY HASH(expression)
      [subpartition_option] PARTITIONS partition_count
    | PARTITION BY KEY([column_name_list])
      [subpartition_option] PARTITIONS partition_count
    | PARTITION BY RANGE {(expression) | COLUMNS (column_name_list)}
      [subpartition_option] (range_partition_list) [STORAGE_CACHE_POLICY = {"hot" | "auto" | "none"}]
    | PARTITION BY LIST {(expression) | COLUMNS (column_name_list)}
      [subpartition_option] PARTITIONS partition_count
    | PARTITION BY RANGE [COLUMNS]([column_name_list]) [SIZE('size_value')] (range_partition_list)

subpartition_option:
      SUBPARTITION BY HASH(expression)
      SUBPARTITIONS subpartition_count
    | SUBPARTITION BY KEY(column_name_list)
      SUBPARTITIONS subpartition_count
    | SUBPARTITION BY RANGE {(expression) | COLUMNS (column_name_list)}
      (range_subpartition_list) [STORAGE_CACHE_POLICY = {"hot" | "auto" | "none"}]
    | SUBPARTITION BY LIST(expression)

timeline_strategy_list:
    BOUNDARY_COLUMN = column_name [,BOUNDARY_COLUMN_UNIT = {"s"| "ms"}] ,HOT_RETENTON = intnum retention_time_unit
retention_time_unit:
    YEAR
    | MONTH
    | WEEK
    | DAY
    | HOUR
    | MINUTE

range_partition_list:
    range_partition [, range_partition ...]

range_partition:
    PARTITION partition_name
    VALUES LESS THAN {(expression_list) | MAXVALUE}
    [STORAGE_CACHE_POLICY = {"hot" | "auto" | "none"}]

range_subpartition_list:
    range_subpartition [, range_subpartition ...]

range_subpartition:
    SUBPARTITION subpartition_name
    VALUES LESS THAN {(expression_list) | MAXVALUE}
    [STORAGE_CACHE_POLICY = {"hot" | "auto" | "none"}]

expression_list:
    expression [, expression ...]

column_name_list:
    column_name [, column_name ...]

partition_name_list:
    partition_name [, partition_name ...]

partition_count | subpartition_count:
    INT_VALUE

table_column_group_option/index_column_group_option:
      WITH COLUMN GROUP(all columns)
    | WITH COLUMN GROUP(each column)
    | WITH COLUMN GROUP(all columns, each column)

index_json_clause:
    [UNIQUE] INDEX idx_json_name((CAST(json_column_name->'$.json_field_name' AS UNSIGNED ARRAY)))
    | INDEX idx_json_name(column_name, [column_name, ...] (CAST(json_column_name->'$.json_field_name' AS CHAR(n) ARRAY)))
```