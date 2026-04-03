// Ported from pages/_shared.py — all design constants

export const PHASE_COLORS: Record<string, string> = {
  '临床I期':   '#90CAF9',
  '临床II期':  '#42A5F5',
  '临床III期': '#1565C0',
  'NDA申请':   '#FF8F00',
  '已上市':    '#2E7D32',
};

export const PHASES = ['临床I期', '临床II期', '临床III期', 'NDA申请', '已上市'] as const;

export const TAG_PILL_COLORS: Record<string, string> = {
  '集采':   '#1A73E8',
  '医保':   '#0F9D58',
  '创新药': '#F4511E',
  '政策':   '#AB47BC',
  '医改':   '#00ACC1',
  '临床':   '#FB8C00',
  '监管':   '#8D6E63',
  '疫苗':   '#546E7A',
  '器械':   '#EC407A',
  'DRG':    '#3949AB',
  'DIP':    '#00897B',
};

export const DEPT_COLORS: Record<string, string> = {
  '国务院':            '#2166AC',
  '国家医疗保障局':    '#1A9641',
  '国家药品监督管理局':'#E7731C',
  '国家卫生健康委员会':'#9B2335',
  '工业和信息化部':    '#6A4C93',
  '国家发展和改革委员会':'#1D6996',
};

export const NHSA_COL_MAP: Record<string, string> = {
  col14:  '医保动态',
  col147: '集采专栏',
  col104: '政策法规',
  col105: '政策解读',
};

export const MODULE_LABELS: Record<string, string> = {
  policy_all:       '产业政策（全部）',
  policy_monthly:   '产业政策（月度）',
  news_monthly:     '行业新闻',
  drugs_monthly:    '药物资讯',
  academic_monthly: '文献总结',
};

export const INDUSTRY_LABELS: Record<string, string> = {
  biomedicine:      '生物医药',
  biomanufacturing: '生物制造',
};

export const COUNTRY_LABELS: Record<string, string> = {
  china:   '中国',
  usa:     '美国',
  japan:   '日本',
  korea:   '韩国',
  germany: '德国',
  uk:      '英国',
  france:  '法国',
  swiss:   '瑞士',
};
