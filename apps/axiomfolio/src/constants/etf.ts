export const ETF_SYMBOLS = [
  'COLO', 'DBA', 'DIA', 'ECH', 'EPOL', 'EPU', 'EWA', 'EWC', 'EWG', 'EWH', 'EWI', 'EWJ', 'EWM', 'EWW',
  'EWY', 'EWZ', 'FUTY', 'FXU', 'GII', 'GLD', 'GREK', 'IDU', 'IFRA', 'IHI', 'INDA', 'ITA', 'ITB', 'IWC',
  'IWM', 'IYR', 'IYT', 'JXI', 'MDY', 'MOO', 'NFRA', 'OIH', 'PALL', 'PAVE', 'PPLT', 'RSPU', 'SDP', 'SHLD',
  'SOX', 'SOXX', 'SPSM', 'SPY', 'UPW', 'USO', 'UTES', 'VPU', 'XBI', 'XHB', 'XLB', 'XLC', 'XLE', 'XLF', 'XLI',
  'XLK', 'XLP', 'XLU', 'XLV', 'XLY', 'XME', 'XOP', 'XRT',
];

export const ETF_SYMBOL_SET = new Set(ETF_SYMBOLS.map((s) => s.toUpperCase()));
