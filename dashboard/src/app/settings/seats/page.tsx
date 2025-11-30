"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Users,
  Image,
  Pencil,
  Check,
  X,
  RefreshCw,
} from "lucide-react";
import { getSeats, updateSeat, populateSeatsFromCreatives } from "@/lib/api";
import type { BuyerSeat } from "@/types/api";
import { formatNumber } from "@/lib/utils";

export default function SeatsSettingsPage() {
  const [seats, setSeats] = useState<BuyerSeat[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState("");
  const [saving, setSaving] = useState(false);
  const [populating, setPopulating] = useState(false);
  const [message, setMessage] = useState<{
    type: "success" | "error";
    text: string;
  } | null>(null);

  useEffect(() => {
    fetchSeats();
  }, []);

  const fetchSeats = async () => {
    setLoading(true);
    try {
      const data = await getSeats({ active_only: false });
      setSeats(data);
    } catch (error) {
      console.error("Failed to fetch seats:", error);
    }
    setLoading(false);
  };

  const handleStartEdit = (seat: BuyerSeat) => {
    setEditingId(seat.buyer_id);
    setEditValue(seat.display_name || "");
  };

  const handleCancelEdit = () => {
    setEditingId(null);
    setEditValue("");
  };

  const handleSaveEdit = async (buyerId: string) => {
    if (!editValue.trim()) {
      setMessage({ type: "error", text: "Display name cannot be empty" });
      return;
    }

    setSaving(true);
    try {
      await updateSeat(buyerId, { display_name: editValue.trim() });
      setSeats((prev) =>
        prev.map((s) =>
          s.buyer_id === buyerId ? { ...s, display_name: editValue.trim() } : s
        )
      );
      setEditingId(null);
      setMessage({ type: "success", text: "Seat name updated" });
    } catch (error) {
      setMessage({ type: "error", text: "Failed to update seat name" });
    }
    setSaving(false);
    setTimeout(() => setMessage(null), 3000);
  };

  const handlePopulate = async () => {
    setPopulating(true);
    try {
      const result = await populateSeatsFromCreatives();
      if (result.seats_created > 0) {
        setMessage({
          type: "success",
          text: `Created ${result.seats_created} new seats from creatives`,
        });
        fetchSeats();
      } else {
        setMessage({ type: "success", text: "All seats are already populated" });
      }
    } catch (error) {
      setMessage({ type: "error", text: "Failed to populate seats" });
    }
    setPopulating(false);
    setTimeout(() => setMessage(null), 3000);
  };

  const totalCreatives = seats.reduce((sum, s) => sum + s.creative_count, 0);

  return (
    <div className="p-8 max-w-4xl">
      <Link
        href="/settings"
        className="inline-flex items-center text-sm text-gray-500 hover:text-gray-700 mb-4"
      >
        <ArrowLeft className="h-4 w-4 mr-1" />
        Back to Settings
      </Link>

      <div className="flex justify-between items-start mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Seat Management</h1>
          <p className="mt-1 text-sm text-gray-500">
            {seats.length} seat{seats.length !== 1 ? "s" : ""} with{" "}
            {formatNumber(totalCreatives)} total creatives
          </p>
        </div>
        <button
          onClick={handlePopulate}
          disabled={populating}
          className="btn-secondary flex items-center gap-2"
        >
          <RefreshCw
            className={`h-4 w-4 ${populating ? "animate-spin" : ""}`}
          />
          {populating ? "Populating..." : "Populate from Creatives"}
        </button>
      </div>

      {message && (
        <div
          className={`mb-6 p-4 rounded-lg ${
            message.type === "success"
              ? "bg-green-50 border border-green-200 text-green-800"
              : "bg-red-50 border border-red-200 text-red-800"
          }`}
        >
          {message.text}
        </div>
      )}

      {loading ? (
        <div className="animate-pulse space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="h-16 bg-gray-100 rounded-lg" />
          ))}
        </div>
      ) : seats.length > 0 ? (
        <div className="bg-white rounded-lg border overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50 border-b">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Buyer ID
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Display Name
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Creatives
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Last Synced
                </th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {seats.map((seat) => (
                <tr key={seat.buyer_id} className="group hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono text-sm text-gray-600">
                    {seat.buyer_id}
                  </td>
                  <td className="px-4 py-3">
                    {editingId === seat.buyer_id ? (
                      <div className="flex items-center gap-2">
                        <input
                          type="text"
                          value={editValue}
                          onChange={(e) => setEditValue(e.target.value)}
                          className="border rounded px-2 py-1 text-sm w-48"
                          autoFocus
                          onKeyDown={(e) => {
                            if (e.key === "Enter") handleSaveEdit(seat.buyer_id);
                            if (e.key === "Escape") handleCancelEdit();
                          }}
                        />
                        <button
                          onClick={() => handleSaveEdit(seat.buyer_id)}
                          disabled={saving}
                          className="p-1 text-green-600 hover:bg-green-50 rounded"
                        >
                          <Check className="h-4 w-4" />
                        </button>
                        <button
                          onClick={handleCancelEdit}
                          className="p-1 text-gray-400 hover:bg-gray-100 rounded"
                        >
                          <X className="h-4 w-4" />
                        </button>
                      </div>
                    ) : (
                      <div className="flex items-center gap-2">
                        <Users className="h-4 w-4 text-gray-400" />
                        <span className="font-medium text-gray-900">
                          {seat.display_name || `Account ${seat.buyer_id}`}
                        </span>
                        <button
                          onClick={() => handleStartEdit(seat)}
                          className="p-1 text-gray-400 hover:text-gray-700 hover:bg-gray-100 rounded opacity-0 group-hover:opacity-100 transition-opacity"
                          title="Edit name"
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1 text-sm">
                      <Image className="h-4 w-4 text-gray-400" />
                      <span>{formatNumber(seat.creative_count)}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-500">
                    {seat.last_synced
                      ? new Date(seat.last_synced).toLocaleDateString()
                      : "Never"}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {editingId !== seat.buyer_id && (
                      <Link
                        href={`/creatives?buyer_id=${seat.buyer_id}`}
                        className="text-sm text-primary-600 hover:text-primary-700"
                      >
                        View Creatives
                      </Link>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="text-center py-12 bg-gray-50 rounded-lg">
          <Users className="mx-auto h-12 w-12 text-gray-400" />
          <h3 className="mt-4 text-lg font-medium text-gray-900">
            No seats found
          </h3>
          <p className="mt-2 text-sm text-gray-500">
            Seats will be created automatically when you import creatives or
            discover seats from the API.
          </p>
          <button
            onClick={handlePopulate}
            disabled={populating}
            className="mt-4 btn-primary"
          >
            Populate from Existing Creatives
          </button>
        </div>
      )}
    </div>
  );
}
