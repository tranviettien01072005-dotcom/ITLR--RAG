import { beforeEach, describe, expect, it, vi } from "vitest";

const db = vi.hoisted(() => ({ query: vi.fn() }));
vi.mock("../db/pool", () => ({ query: db.query }));

import { acceptedFriendIds, areFriends, friendStatus, parseYouTubeId } from "./social";

beforeEach(() => db.query.mockReset());

describe("parseYouTubeId", () => {
  it.each([
    ["https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10", "dQw4w9WgXcQ"],
    ["https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"],
    ["https://youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"],
    ["https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"],
    ["  dQw4w9WgXcQ ", "dQw4w9WgXcQ"],
  ])("extracts %s", (input, expected) => {
    expect(parseYouTubeId(input)).toBe(expected);
  });

  it.each(["", "short", "javascript:alert(1)", "https://evil.test/dQw4w9WgXcQ"])(
    "rejects %s",
    (input) => {
      expect(parseYouTubeId(input)).toBeNull();
    },
  );
});

describe("friendStatus", () => {
  it("returns self without querying", async () => {
    await expect(friendStatus(3, 3)).resolves.toBe("self");
    expect(db.query).not.toHaveBeenCalled();
  });

  it("maps accepted, pending and missing rows", async () => {
    db.query.mockResolvedValueOnce([]);
    await expect(friendStatus(1, 2)).resolves.toBe("none");

    db.query.mockResolvedValueOnce([{ requester_id: 1, status: "accepted" }]);
    await expect(friendStatus(1, 2)).resolves.toBe("friends");

    db.query.mockResolvedValueOnce([{ requester_id: 1, status: "pending" }]);
    await expect(friendStatus(1, 2)).resolves.toBe("pending_out");

    db.query.mockResolvedValueOnce([{ requester_id: 2, status: "pending" }]);
    await expect(friendStatus(1, 2)).resolves.toBe("pending_in");
  });
});

it("acceptedFriendIds maps rows and areFriends reflects row presence", async () => {
  db.query.mockResolvedValueOnce([{ id: 4 }, { id: 7 }]);
  await expect(acceptedFriendIds(1)).resolves.toEqual([4, 7]);

  db.query.mockResolvedValueOnce([{ "?column?": 1 }]);
  await expect(areFriends(1, 4)).resolves.toBe(true);

  db.query.mockResolvedValueOnce([]);
  await expect(areFriends(1, 5)).resolves.toBe(false);
});
