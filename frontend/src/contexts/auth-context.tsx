"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import {
  getMe,
  login as apiLogin,
  logout as apiLogout,
  refreshToken,
  setAccessToken,
  type LoginData,
  type UserProfile,
} from "@/lib/api-client";

interface AuthContextType {
  user: UserProfile | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (data: LoginData) => Promise<void>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const refreshUser = useCallback(async () => {
    try {
      const profile = await getMe();
      setUser(profile);
    } catch {
      setUser(null);
      setAccessToken(null);
    }
  }, []);

  // On mount: try to refresh the access token using the httpOnly cookie
  useEffect(() => {
    async function init() {
      try {
        await refreshToken();
        await refreshUser();
      } catch {
        // No valid refresh token — user is not logged in
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    }
    init();
  }, [refreshUser]);

  const login = useCallback(
    async (data: LoginData) => {
      await apiLogin(data);
      await refreshUser();
    },
    [refreshUser]
  );

  const logout = useCallback(async () => {
    try {
      await apiLogout();
    } catch {
      // Clear local state even if server logout fails
    }
    setUser(null);
    setAccessToken(null);
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: user !== null,
        isLoading,
        login,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
