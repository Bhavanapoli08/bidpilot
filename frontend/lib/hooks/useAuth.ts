"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, tokenStore } from "@/lib/api/client";

interface AuthUser {
  id: string;
  email: string;
  role: string;
}

/**
 * Resolves the current user and guards a route.
 * Redirects to /auth/login if no valid token is present.
 */
export function useAuth(redirectIfUnauthed = true) {
  const router = useRouter();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;

    async function load() {
      if (!tokenStore.access) {
        if (redirectIfUnauthed) router.push("/auth/login");
        setLoading(false);
        return;
      }
      try {
        const { data } = await api.me();
        if (active) setUser(data);
      } catch {
        tokenStore.clear();
        if (redirectIfUnauthed) router.push("/auth/login");
      } finally {
        if (active) setLoading(false);
      }
    }

    load();
    return () => {
      active = false;
    };
  }, [router, redirectIfUnauthed]);

  const logout = () => {
    tokenStore.clear();
    router.push("/auth/login");
  };

  return { user, loading, logout };
}
