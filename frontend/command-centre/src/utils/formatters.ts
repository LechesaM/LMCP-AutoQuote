export function formatCurrency(value, { minimumFractionDigits = 0, maximumFractionDigits = 0 } = {}) {
  const numberValue = Number(value || 0);
  return new Intl.NumberFormat("en-ZA", {
    style: "currency",
    currency: "ZAR",
    minimumFractionDigits,
    maximumFractionDigits,
  }).format(numberValue);
}

export function formatPercent(value, fractionDigits = 1) {
  const numberValue = Number(value || 0);
  return `${numberValue.toFixed(fractionDigits)}%`;
}

export function formatInteger(value) {
  return new Intl.NumberFormat("en-ZA", { maximumFractionDigits: 0 }).format(Number(value || 0));
}
