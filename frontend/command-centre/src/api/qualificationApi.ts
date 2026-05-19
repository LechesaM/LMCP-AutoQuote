import { rfqRules } from "../utils/tenderFilters";
import { fetchQualificationSummaryData } from "./qualificationClient";

export async function fetchQualificationRules() {
  return rfqRules;
}

export async function fetchQualificationSummary() {
  return fetchQualificationSummaryData();
}
