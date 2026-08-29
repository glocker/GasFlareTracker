export interface FacilityProperties {
  name: string;
  kind: string;
  operator: string | null;
  status: "no_data" | "silent" | "elevated" | "reduced" | "normal";
}

export interface FlareEvent {
  id: number;
  facility_id: number;
  facility_name: string;
  kind: "spike" | "regime_up" | "regime_down";
  start_date: string;
  end_date: string | null;
  peak_frp: number;
  baseline_frp: number;
  score: number;
  blind_nights: number;
}

// facility selected event detail (set when opened from event feed card)
export interface FacilitySelection extends FacilityProperties {
  event?: FlareEvent;
}
