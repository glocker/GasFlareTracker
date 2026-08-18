export interface FacilityProperties {
  name: string;
  kind: string;
  operator: string | null;
  status: "no_data" | "silent" | "elevated" | "reduced" | "normal";
}
